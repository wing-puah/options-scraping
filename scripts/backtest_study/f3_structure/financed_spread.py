"""Financed debit verticals: does selling premium against the debit improve the outcome?

The operator's hypothesis is the classic one: a debit vertical costs premium, so
sell something against it. Three ways to sell it, plus a strike-aligned control:

  F0  the counterpart-mirror same-direction credit at the debit's OWN two
      strikes (zero scrape — the mirrors are already cached). Algebraically a
      doubled-delta synthetic forward capped at +/-(K2-K1), and a legitimate
      answer to "same-direction financing".
  F1  an opposite-delta credit spread beyond the outer strike, OTM direction.
  F2  a naked short leg beyond the outer strike. UNBOUNDED.
  F3  a same-direction credit vertical on the other side of spot.
  F4  AMENDMENT 1 — diagonal financing: ONE short-dated, delta-targeted naked
      short leg beyond the outer strike, at a NEARER expiry than the debit.
      Sold once at entry ("not to be reached"), never rolled.
      AMENDMENT 2 — that leg is MANAGED, not held: bought back at 50% of the
      credit (`mgmt-pt50`) or at $100 on the tranche (`mgmt-$100`), stopped at
      2x credit against on both, with a `hold` comparison cell that attributes
      any effect to the management rule rather than the structure. Six cells,
      {d10,d20} x {pt50,$100,hold}, on the SAME rows. Whatever is still open at
      the near expiry is bought back at its LAST REAL MARK — never dropped to
      zero, on every cell.

This is a STRUCTURE question (f3), the `bear_rewrap` shape: same signal, same
entry day, same shipped exits, different wrapper. It is NOT a selection study —
no arm changes WHICH signals are taken — and NOT an exit study; every synthetic
replays under the shipped profiles through the frozen harness.

THE REGISTERED READING THAT IS NOT A P&L READING
------------------------------------------------
`vol_sleeve` is the precedent: synthesizing on the engine's own signal dates can
re-wrap the SAME exposure. A wrapper that clears every R gate but correlates
POSITIVELY with the deployed sleeve is a RE-WRAP, not a diversifier, and is
recorded as such regardless of its dR (E3). That is criterion 7 of a seven-part
conjunction, and it is pre-registered as a criterion, not a caveat.

WHAT THIS MODULE OWNS AND WHAT IT BORROWS
-----------------------------------------
Pricing is `bear_rewrap`'s path VERBATIM BY IMPORT (`leg_details`, `leg_series`,
`entry_date_for`, `entry_price_of`, `net_entry`, `net_marks` with the
`_defined_risk_bounds` clamp, `synth_trade`, `reconstructs`, `cached_puts`) —
the `calendar_hedge` precedent. `bear_rewrap` is never edited: its published
cell means are pinned by `calendar_hedge`. `cached_calls` is the one sibling
helper this module adds, because `bear_rewrap` only ever needed the put ladder.

Sizing is NOT borrowed. `bear_rewrap.size_contracts` is debit-only, and three of
the four shapes here can flip the net to a credit; a credit sized on the premium
RECEIVED is the original oversizing bug. `size_contracts()` below is
`scripts/backtest/simulate.py::_size_contracts` ported verbatim, structural max
loss and all, with a `--fixed-contracts` control printed alongside so the sizing
sensitivity is visible rather than assumed away. Contracts are not a reporting
detail: `harness.replay`'s dollar_stop is an ABSOLUTE $1,000 cap, so a synthetic
priced at a different premium and left at the baseline's contract count is
handed a different effective stop.

Exits are assigned by the SIGN of the synthetic net entry — debit-signed to the
shipped debit profile (including the bear-keyed `be_after 0.50` where the
BASELINE row carries it), credit-signed to `CREDIT_PROD`. The debit/credit flip
share is reported per shape BEFORE any dR is read: a shape that flips half its
rows to the credit profile has changed the exit rule as well as the wrapper.

F4 needs contracts at an expiry the book never traded, so it depends on a
scrape (`scripts/collector/fetch_financing_legs.py`, categories `fin_diag_call`
/ `fin_diag_put`). Until those are cached the F4 section prints its coverage
census and the cells carry the verdict AWAITING SCRAPE — never a crash, never a
silently absent arm, and never a conclusion drawn from an unscraped cell.

Read-only. Touches no config, writes no tab, scrapes nothing. Run:

    python -m scripts.backtest_study run financed_spread --era v3

Binding spec: research/pre-registrations/f3_structure/financed_spread.md (written before this
module existed). Where this module deviates from it, it says so on the page —
see G2's naked-short-put note.
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.parsing import to_float  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.helpers import (  # noqa: E402
    _defined_risk_bounds, _max_loss_per_unit, _price_asof,
)
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.f2_management.bear_giveback import (  # noqa: E402
    cell_stats, fmt_row, hdr, prod_profile_for, sub,
)
from scripts.backtest_study.f3_structure import bear_rewrap as BR  # noqa: E402
from scripts.backtest_study.lib import greeks as GK  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib.book import CREDIT_PROD, load_book  # noqa: E402
from scripts.backtest_study.lib.harness import Trade, replay  # noqa: E402

# Exit codes this study returns as a DESIGNED refusal rather than a failure:
# 2 = the era is too thin to conclude from, 3 = `load_book`'s era guard refusing
# an export set that is not the era asked for. `run.py` reads this by AST parse
# and never imports the module, so it MUST stay a literal module-level
# assignment — an alias to `era.DESIGNED_REFUSAL_EXIT_CODES` or a `frozenset(...)`
# CALL would be invisible to the parse, and a correct refusal would be reported
# as FAILED with its report deleted. A gate failure (G2 clamp attribution, E1
# geometry) is a REAL failure and exits 1, not a refusal.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3}

EXIT_GATE_FAILED = 1

# ── pre-registered constants (frozen; do not tune) ───────────────────────────

SHAPES = ("F0", "F1", "F2", "F3", "F4")
OFFSETS = (1, 2)

# F0 sits at the debit's OWN strikes, so the strike-offset axis is degenerate
# for it — it is one cell, labelled `own`, not two. Every other shape runs at
# offset 1 (nearest cached strike beyond) and offset 2 (one further out). No
# third offset, no fifth shape.
# F4's second axis is not a strike offset at all but a |Delta| TARGET, so its
# cells are keyed by the target in delta-points (10 / 20) — `cell_label` prints
# them as the registered `F4-d10` / `F4-d20`, and `build()` reads the key back
# as `offset / 100`.
DIAG_MIN_DAYS = 7          # near expiry >= 7 calendar days after entry ...
DIAG_MAX_DTE_FRAC = 0.5    # ... and <= 1/2 the debit's DTE at entry
DIAG_N_CANDIDATES = 4      # the 4 nearest cached strikes strictly beyond the outer leg
DIAG_TARGETS = (0.10, 0.20)   # the two registered |Delta| targets
DIAG_DELTA_TOL = 0.10      # closest candidate off-target by MORE than this -> excluded

# AMENDMENT 2 — F4 management. The operator's stated practice, registered
# before any F4 number existed and FROZEN: buy the financing leg back once it
# has earned 50% of the credit "or at least $100", stop it at 2x credit
# against. Two parallel profit-trigger bases (the staged_exit twin-cut
# precedent — NEITHER has precedence, both report side by side) plus a
# hold-to-expiry comparison cell that attributes any effect to the MANAGEMENT
# rule rather than the structure. No trigger value may be tuned after a number
# is seen.
MGMT = ("pt50", "d100", "hold")
MGMT_LABEL = {"pt50": "mgmt-pt50", "d100": "mgmt-$100", "hold": "hold"}
MGMT_DESC = {
    "pt50": "buy back at the first session whose mark <= 0.50 x entry credit",
    "d100": "buy back at the first session where (credit - mark) x 100 x contracts >= $100",
    "hold": "no management — held to the near expiry (comparison cell)",
}
PT50_FRAC = 0.50           # profit take, mgmt-pt50
PROFIT_DOLLARS = 100.0     # profit take, mgmt-$100 (per tranche, at the simulated count)
LOSS_MULT = 2.0            # loss stop, BOTH mgmt bases
FORGIVEN_MARK = 0.05       # the amendment-1 "forgiven value" reporting threshold

# The cell key is (shape, offset, mgmt). The third slot is "" for F0-F3, which
# have no management axis, and one of MGMT for F4: amendment 2 crosses the two
# |Delta| targets with three management rules on the SAME underlying rows, so
# the six F4 cells cost no power against each other.
CELLS: list[tuple[str, int, str]] = [("F0", 0, "")] + [
    (s, o, "") for s in ("F1", "F2", "F3") for o in OFFSETS
] + [("F4", int(round(t * 100)), m) for t in DIAG_TARGETS for m in MGMT]

SHAPE_DESC = {
    "F0": "strike-aligned control — counterpart mirror at the debit's own strikes",
    "F1": "opposite-delta credit spread beyond the outer strike (OTM direction)",
    "F2": "naked short leg beyond the outer strike — UNBOUNDED",
    "F3": "same-direction credit vertical on the other side of spot",
    "F4": "diagonal financing — one short-dated delta-targeted naked short leg, "
          "managed",
}

# G0 power floor, declared in the registration before any cell was built.
MIN_DATES = 25
MIN_ROWS = 60

# Degenerate-premium guard. `Trade.denom = abs(entry_net)`, so a financed net
# near zero makes R explode — and shrinking the debit is this structure's whole
# purpose, which is exactly why the guard has to be explicit and counted.
MIN_ABS_NET = 0.10

# Production sizing config, transcribed from config/backtest.yml
# (portfolio_value 50000, risk_per_trade_pct 0.02, stop_loss 0.75). Same three
# numbers `bear_rewrap` transcribes; the FORMULA below is the difference.
PORTFOLIO_VALUE = 50000.0
RISK_PER_TRADE_PCT = 0.02
STOP_LOSS = 0.75

# The registered E1 geometry expectation, per shape. F2's is deliberately absent:
# the registration pins F1 (must reduce |net delta|) and F0/F3 (must increase
# it); a naked short's direction is reported, not gated.
# F4's expectation is registered by amendment 1: |net delta| must DECREASE
# (the short leg is sold against the debit's own direction).
E1_EXPECT = {"F0": +1, "F1": -1, "F3": +1, "F4": -1}

# E3 / P2 convention, inherited from bear_rewrap's ARM P.
MIN_SHARED_DATES = 8

# The verdict vocabulary, worded in the registration. Nothing else may be printed
# as a verdict.
VERDICTS = ("CANDIDATE", "RE-WRAP", "NULL", "UNDERPOWERED", "AWAITING SCRAPE")

# The under-the-floor token: too few dates to judge — census printed, nothing
# concluded. Amendment 1 introduced it for F4 alone, while F0-F3 kept the older
# "POWER-STOPPED" wording their already-published reports quoted. The repo
# retired that wording on 2026-08-22, so every shape prints this one token now;
# a report dated before then says POWER-STOPPED and means exactly this. Reports
# and registrations already on disk are NOT rewritten — they quote what ran.
UNDERPOWERED = "UNDERPOWERED"


# ── the one helper bear_rewrap does not have ─────────────────────────────────

def cached_calls(ticker: str, expiration: date) -> list[float]:
    """Strikes of every cached CALL on one (ticker, expiry), ascending.

    Sibling of `bear_rewrap.cached_puts`, added HERE rather than there: that
    module is imported by `calendar_hedge` and its published cell means are
    pinned, so it is read-only for this study. Candidate strikes come from the
    ticker's OBSERVED cached ladder — never an invented increment.
    """
    prefix = f"{ticker.upper().strip()}_{expiration.strftime('%Y%m%d')}_"
    out = []
    for path in HISTORY_CACHE.glob(f"{prefix}*C.csv"):
        try:
            out.append(float(path.stem.split("_")[-1][:-1]))
        except ValueError:
            continue
    return sorted(out)


def _opposite(opt_type: str) -> str:
    return "Put" if opt_type == "Call" else "Call"


# ── sizing: scripts/backtest/simulate.py::_size_contracts, ported verbatim ───

def size_contracts(entry_net: float, legs: list[Leg]) -> tuple[int, bool]:
    """`(contracts, hit_unbounded_fallback)` — production fixed-fractional sizing.

    Ported from `scripts/backtest/simulate.py::_size_contracts` (the sim_cfg
    lookups replaced by this module's transcribed constants; the arithmetic,
    the branch order and the `max(1, floor(...))` rounding are unchanged):

      debit  (entry_net > 0): risk budget / (premium x 100 x stop_loss).
      credit (entry_net < 0): risk budget / (STRUCTURAL max loss x 100). Sized on
             `_max_loss_per_unit`, never on the credit received — a small credit
             on a wide or naked structure understates the true worst case, which
             is the original oversizing bug.
      credit whose max loss cannot be bounded (F2's naked short call,
             multi-expiration credit): 1 contract, the production convention.
             The portfolio dollar_stop still caps the realized loss.

    `bear_rewrap.size_contracts` is NOT used: it is the debit branch only, and
    three of the four shapes here can flip the net to a credit.
    """
    dollar_risk = PORTFOLIO_VALUE * RISK_PER_TRADE_PCT

    if entry_net < 0:
        mlpu = _max_loss_per_unit(legs, entry_net)
        if mlpu is not None and mlpu > 0:
            return max(1, math.floor(dollar_risk / (mlpu * 100))), False
        return 1, True

    if STOP_LOSS > 0 and entry_net > 0:
        loss_per_contract = entry_net * 100 * STOP_LOSS
        return max(1, math.floor(dollar_risk / loss_per_contract)), False
    return 1, False


# ── population ───────────────────────────────────────────────────────────────

def direction_of(legs: list[Leg]) -> str | None:
    """`"bull"` / `"bear"` for a debit-signed two-leg vertical, else None.

    Read off the GEOMETRY, not off the row's `structure` label: the label is a
    classifier output and the strike ladder is not. A debit-signed call vertical
    is long the lower strike (bullish); a debit-signed put vertical is long the
    higher strike (bearish). Anything else is not a debit vertical and is
    excluded and counted.
    """
    longs = [lg for lg in legs if lg.qty > 0]
    shorts = [lg for lg in legs if lg.qty < 0]
    if len(longs) != 1 or len(shorts) != 1:
        return None
    lo, sh = longs[0], shorts[0]
    if lo.opt_type != sh.opt_type:
        return None
    if lo.opt_type == "Call" and lo.strike < sh.strike:
        return "bull"
    if lo.opt_type == "Put" and lo.strike > sh.strike:
        return "bear"
    return None


def population(recs: list[dict]) -> tuple[list[tuple[dict, str]], Counter]:
    """Two-leg single-expiry DEBIT verticals, with the exclusion census."""
    keep: list[tuple[dict, str]] = []
    why: Counter = Counter()
    for rec in recs:
        legs = rec["t"].legs or []
        why["book_rows"] += 1
        if len(legs) != 2:
            why["excl_not_two_leg"] += 1
            continue
        if len({lg.expiration for lg in legs}) != 1:
            why["excl_multi_expiry"] += 1
            continue
        if rec["credit"]:
            why["excl_credit_signed"] += 1
            continue
        d = direction_of(legs)
        if d is None:
            why["excl_not_a_debit_vertical"] += 1
            continue
        keep.append((rec, d))
        why[f"kept_{d}"] += 1
    return keep, why


# ── the four shapes ──────────────────────────────────────────────────────────

def _otm_ladder(legs: list[Leg], dirn: str) -> list[float]:
    """Cached strikes strictly BEYOND the outer strike, in the OTM direction.

    bull (call debit): calls ABOVE the highest leg strike, ascending.
    bear (put debit):  puts BELOW the lowest leg strike, descending.
    """
    tk, exp = legs[0].ticker, legs[0].expiration
    if dirn == "bull":
        outer = max(lg.strike for lg in legs)
        return [k for k in cached_calls(tk, exp) if k > outer]
    outer = min(lg.strike for lg in legs)
    return [k for k in reversed(BR.cached_puts(tk, exp)) if k < outer]


def _other_side_ladder(legs: list[Leg], dirn: str) -> list[float]:
    """Cached strikes on the OTHER side of spot from the debit.

    bull (call debit): puts BELOW the lowest leg strike, descending.
    bear (put debit):  calls ABOVE the highest leg strike, ascending.
    """
    tk, exp = legs[0].ticker, legs[0].expiration
    if dirn == "bull":
        inner = min(lg.strike for lg in legs)
        return [k for k in reversed(BR.cached_puts(tk, exp)) if k < inner]
    inner = max(lg.strike for lg in legs)
    return [k for k in cached_calls(tk, exp) if k > inner]


def _ladder_type(dirn: str, side: str) -> str:
    """The option type a ladder is drawn from."""
    if side == "otm":
        return "Call" if dirn == "bull" else "Put"
    return "Put" if dirn == "bull" else "Call"


def build_legs(rec: dict, dirn: str, shape: str, offset: int) -> list[Leg] | None:
    """The financed leg set for one (row, shape, offset), or None if unbuildable.

    Financing legs always share the debit's expiry (the population is
    single-expiry by construction), so `_defined_risk_bounds` stays applicable
    to every bounded shape and the harness grid is unchanged.
    """
    base = list(rec["t"].legs)
    unit = abs(next(lg.qty for lg in base if lg.qty > 0))
    exp = base[0].expiration
    tk = base[0].ticker

    if shape == "F0":
        # The counterpart mirror: same strike, same sign, opposite type. For a
        # bull_call (+C(K1), -C(K2)) that adds (+P(K1), -P(K2)) — a bull_put
        # credit at the SAME strikes, which sums to long straddle K1 - short
        # straddle K2: a doubled-delta synthetic forward capped at +/-(K2-K1).
        mirror = [Leg(qty=lg.qty, ticker=lg.ticker, expiration=lg.expiration,
                      strike=lg.strike, opt_type=_opposite(lg.opt_type))
                  for lg in base]
        return base + mirror

    if shape in ("F1", "F2"):
        ladder, side = _otm_ladder(base, dirn), "otm"
    else:
        ladder, side = _other_side_ladder(base, dirn), "other"
    opt = _ladder_type(dirn, side)

    if shape == "F2":
        if len(ladder) < offset:
            return None
        return base + [Leg(qty=-unit, ticker=tk, expiration=exp,
                           strike=ladder[offset - 1], opt_type=opt)]

    # F1 / F3: a credit spread — short the nearer strike, long the one beyond.
    if len(ladder) < offset + 1:
        return None
    short_k, long_k = ladder[offset - 1], ladder[offset]
    return base + [
        Leg(qty=-unit, ticker=tk, expiration=exp, strike=short_k, opt_type=opt),
        Leg(qty=+unit, ticker=tk, expiration=exp, strike=long_k, opt_type=opt),
    ]


# ── F4 — diagonal financing (AMENDMENT 1) ────────────────────────────────────
#
# Registered AFTER the F0-F3 run returned NULL on all seven same-expiry cells
# and closed them. Nothing here reopens those cells on these dates: F4 is a
# DIFFERENT structure the original arms never priced — a short-dated,
# delta-targeted naked short leg, premium sold "not to be reached" and expiring
# while the debit thesis is still developing.

_ticker_expiries_cache: dict[str, list[date]] = {}


def cached_ticker_expiries(ticker: str) -> list[date]:
    """Every expiry this ticker has ANY cached contract at, ascending.

    "The ticker's cached expiry set" of the amendment's near-expiry window. A
    near expiry is no more invented than a strike is: if nothing is cached in
    the window the row is excluded and counted (`no_near_expiry`), never
    fabricated onto the nearest Friday. Memoised because the population scans
    it once per row.
    """
    tk = ticker.upper().strip()
    if tk not in _ticker_expiries_cache:
        out: set[date] = set()
        for path in HISTORY_CACHE.glob(f"{tk}_*.csv"):
            parts = path.stem.split("_")
            if len(parts) != 3 or parts[0] != tk:
                continue
            stamp = parts[1]
            try:
                out.add(date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8])))
            except (ValueError, IndexError):
                continue
        _ticker_expiries_cache[tk] = sorted(out)
    return _ticker_expiries_cache[tk]


def near_expiry_for(entry_day: date, dte_at_entry: int,
                    expiries) -> date | None:
    """The F4 near expiry, or None (the `no_near_expiry` exclusion).

    Amendment 1, frozen: the NEAREST expiry in the ticker's cached expiry set
    that is >= DIAG_MIN_DAYS calendar days after entry AND <= half the debit's
    DTE at entry. Both ends are anchored on the ENTRY DAY, so `dte_at_entry` is
    the debit's remaining life AT THE FILL — `(debit expiry - entry_day).days`
    — rather than the book's signal-date-based `dte_entry` column; measuring
    one end of a window from the signal and the other from the fill would make
    the window's width depend on the entry lag.

    Shared with `scripts/collector/fetch_financing_legs.py`, which imports this
    function so the scrape targets and the study's construction can never
    disagree about which expiry a row is owed.
    """
    lo = entry_day + timedelta(days=DIAG_MIN_DAYS)
    hi = entry_day + timedelta(days=int(dte_at_entry * DIAG_MAX_DTE_FRAC))
    inside = sorted(e for e in expiries if lo <= e <= hi)
    return inside[0] if inside else None


def f4_row_plan(rec: dict, dirn: str, entry_day: date | None) -> tuple:
    """`(near_expiry, candidate_strikes, opt_type, reason)` for one row.

    The candidate set BEFORE the delta pick, shared by both F4 cells and by the
    coverage census so the two can never disagree about what the scrape owes
    this row. Candidates are the DIAG_N_CANDIDATES nearest strikes CACHED AT
    THE NEAR EXPIRY strictly beyond the debit's outer leg (calls above for a
    bull base, puts below for a bear base) — never an invented strike, and
    never a strike borrowed from another expiry. `reason` is "ok" or the census
    key of the exclusion.
    """
    base = rec["t"].legs
    tk, exp = base[0].ticker, base[0].expiration
    if entry_day is None:
        return None, [], None, "skip_no_common_entry_day"
    dte = (exp - entry_day).days
    if dte <= 0:
        return None, [], None, "skip_no_near_expiry"
    near = near_expiry_for(entry_day, dte, cached_ticker_expiries(tk))
    if near is None:
        return None, [], None, "skip_no_near_expiry"
    if dirn == "bull":
        outer = max(lg.strike for lg in base)
        ks = [k for k in cached_calls(tk, near) if k > outer][:DIAG_N_CANDIDATES]
        opt = "Call"
    else:
        outer = min(lg.strike for lg in base)
        ks = [k for k in reversed(BR.cached_puts(tk, near))
              if k < outer][:DIAG_N_CANDIDATES]
        opt = "Put"
    if not ks:
        return near, [], opt, "skip_no_cached_candidate"
    return near, ks, opt, "ok"


def build_f4(rec: dict, plan: tuple, target: float,
             entry_day: date | None) -> tuple[list[Leg] | None, str]:
    """`(legs, reason)` — the debit plus ONE short leg at the |Delta| target.

    The pick is the candidate whose SCRAPED entry-day |Delta| (per contract, via
    `lib/greeks.py::leg_greek` on the same cached CSV the pricing reads) is
    closest to `target`. Closest candidate off-target by more than
    DIAG_DELTA_TOL is `target_unreachable` — excluded and counted, never
    silently filled with a leg the registration did not ask for. A candidate
    with no entry-day Delta cell is not a zero-delta candidate: it is skipped.

    ZERO-FILLED GREEK ROWS ARE NOT A DELTA OF ZERO. Barchart writes a session
    with `IV,Delta,Gamma,Theta,Vega,Rho,Theo` all literally `0` when it has no
    greek set for that day — the contract still prints a price, and the very
    next row carries real greeks (COIN 2026-03-27 255P: 03-19 all-zero at a
    mark of 53.25, 03-16 Delta -0.9639). Read literally, such a row makes a
    deep-ITM option look like a 0.00-delta one, which lands INSIDE the d10
    cell's tolerance and buys a $53 put as "financing". That is the repo's
    central invariant — a missing greek is None, never 0.0 — so a candidate
    whose entry-day row carries no IV is treated as HAVING NO MEASURED DELTA
    and skipped, counted as `greeks_absent`. It is detected on IV rather than
    on Delta because a genuinely far-OTM option may legitimately round its
    delta to 0.00 while still quoting an IV.
    """
    near, ks, opt, reason = plan
    if reason != "ok" or entry_day is None:
        return None, reason
    base = list(rec["t"].legs)
    unit = abs(next(lg.qty for lg in base if lg.qty > 0))
    tk = base[0].ticker
    best: Leg | None = None
    best_gap: float | None = None
    n_sentinel = 0
    for k in ks:
        leg = Leg(qty=-unit, ticker=tk, expiration=near, strike=k, opt_type=opt)
        row = BR.leg_details(leg).get(entry_day)
        if row is not None and not to_float(row.get("IV")):
            n_sentinel += 1
            continue                     # zero-filled greek row: no measured delta
        d = GK.leg_greek(leg, entry_day, "Delta")
        if d is None:
            continue
        # leg_greek is signed and qty-SCALED; the target is a per-contract |Delta|.
        gap = abs(abs(d) / unit - target)
        if best_gap is None or gap < best_gap:
            best, best_gap = leg, gap
    if best is None:
        return None, ("skip_greeks_absent" if n_sentinel else "skip_no_entry_delta")
    if best_gap > DIAG_DELTA_TOL:
        return None, "skip_target_unreachable"
    return base + [best], "ok"


def f4_entry_credit(short_leg: Leg, day: date) -> float | None:
    """The financing leg's PER-CONTRACT entry credit (positive), on the same
    fill convention `net_entry` used to form `entry_net`. Every amendment-2
    trigger is quoted against this number, so it must be that exact price and
    not a same-day mark."""
    return BR.entry_price_of(short_leg, day)


def f4_last_short_mark(short_leg: Leg) -> float | None:
    """The short leg's last cached mark on or before its own expiry."""
    ms = [m for d, m in BR.leg_series(short_leg) if d <= short_leg.expiration]
    return ms[-1] if ms else None


def f4_buyback(short_leg: Leg, grid: list[date], entry_day: date, credit: float,
               contracts: int, mgmt: str) -> tuple[date | None, float | None, str]:
    """`(session, per-contract cost, reason)` — when the financing leg is closed.

    AMENDMENT 2, frozen (0.50, $100 and 2x are the operator's stated practice
    and may not be tuned after a number is seen):

      pt50   first session whose mark <= PT50_FRAC x entry credit
      d100   first session where (credit - mark) x 100 x contracts >= $100 for
             the TRANCHE (contracts x the leg's per-unit qty; under the
             1-contract naked convention this is per-contract)
      stop   BOTH mgmt bases: first session whose mark >= LOSS_MULT x credit
      hold   no trigger at all — the comparison cell

    Triggers evaluate on the leg's OWN cached daily bars, so a day the contract
    did not print is simply not a trigger day and the test defers to the next
    priced session. That is deliberate rather than `_price_asof`'s carry: a
    carried mark is a stale quote, and letting a stale quote fire a buyback
    would book a fill at a price the market never printed that day.

    The entry session itself is EXCLUDED from the scan (a build decision, not a
    registered rule, disclosed on the page and counted): the credit is that
    day's fill and its close is another quote of the same session, so a trigger
    there is an Open-vs-mark spread artifact rather than the decay the rule is
    written about.

    Whatever has not fired by the near expiry is closed there at the leg's LAST
    REAL MARK (`residual_expiry`) — amendment 2 supersedes amendment 1's
    drop-to-zero, which forgave assignment. A near expiry beyond the end of the
    debit's path window (a long-dated debit truncated by the 120-day path cap)
    leaves the leg open for the whole path: `open_at_grid_end`, no buyback.
    """
    near = short_leg.expiration
    unit = abs(short_leg.qty)
    if mgmt != "hold":
        own = dict(BR.leg_series(short_leg))     # real bars only, never carried
        tranche = max(1, contracts) * unit
        for day in grid:
            if day > near:
                break
            if day <= entry_day:
                continue
            m = own.get(day)
            if m is None:
                continue                          # defers to the next priced session
            if m >= LOSS_MULT * credit:
                return day, m, "stop"
            if mgmt == "pt50" and m <= PT50_FRAC * credit:
                return day, m, "pt50"
            if mgmt == "d100" and (credit - m) * 100 * tranche >= PROFIT_DOLLARS:
                return day, m, "d100"

    after = [d for d in grid if d > near]
    if not after:
        return None, None, "open_at_grid_end"
    last = f4_last_short_mark(short_leg)
    if last is None:
        # Unreachable in practice (the leg priced at entry, so it has a bar),
        # and if it ever happened, closing at the credit books zero P&L on the
        # leg rather than inventing one.
        return after[0], credit, "residual_no_mark"
    return after[0], last, "residual_expiry"


def f4_net_marks(base_legs: list[Leg], short_leg: Leg, grid: list[date],
                 buyback: tuple[date | None, float | None, str]) -> list[float | None]:
    """Daily signed net over the DEBIT's grid for the F4 synthetic.

    Two segments, and the boundary is now the BUYBACK session (amendment 2)
    rather than the near expiry — which for a `hold` cell is the first grid day
    after the near expiry, so amendment 1's segmentation is the special case.

      * WHILE THE LEG IS OPEN (day < buyback session) the position is the debit
        PLUS the live short leg, and it is NOT clamped: `_defined_risk_bounds`
        is a single-expiration payoff function and returns None for a
        two-expiry leg set by design. That is G2's F4 clause, "unclamped while
        the short leg lives", not a missing clamp.
      * FROM THE BUYBACK SESSION ONWARD the short leg is CLOSED and its
        contribution becomes a CONSTANT realized cost, not zero and not a
        carried-forward live mark. The position is a plain single-expiry debit
        again, so the clamp applies — to the DEBIT's own value, with the
        realized constant added outside it (a realized cash amount is not an
        option value and has no arbitrage bound).

    THE ALGEBRA, worked by hand. `Trade.pnl_of(M) = (M - entry_net)/|entry_net|`,
    and `entry_net = D_e - u*C_e` (u = the leg's per-unit qty, C_e = the entry
    credit per contract). At a day after a buyback at cost C_b the true P&L per
    unit is the debit's move PLUS the leg's REALIZED gain:

        pnl = [D(t) - D_e] + u*[C_e - C_b]
            = [D(t) - u*C_b] - [D_e - u*C_e]
            = M(t) - entry_net        with  M(t) = D(t) - u*C_b

    so the mark series carries `short_leg.qty * C_b` (qty is negative) as a
    constant from the buyback session on. Numerically: D_e = 3.00, C_e = 0.80,
    u = 1 -> entry_net = 2.20. Day 5 with D = 3.50 and the leg marked 0.30 is
    M = 3.50 - 0.30 = 3.20, pnl = (3.20-2.20)/2.20 = +0.455 (debit +0.50, leg
    +0.50, on a 2.20 basis). pt50 fires that day at 0.30, so day 6 with
    D = 3.60 is M = 3.60 - 0.30 = 3.30, pnl = +0.500 (debit +0.60, leg's +0.50
    now realized and frozen) — whereas the `hold` cell, with the leg still
    marked at say 0.25, would print M = 3.35 and pnl = +0.523. Note that ON the
    buyback session M is identical either way (C(b) IS C_b): the buyback adds
    no discontinuity, it only stops the leg from moving afterwards.
    """
    b_day, b_cost, _reason = buyback
    legs = list(base_legs) + [short_leg]
    series = {id(leg): BR.leg_series(leg) for leg in legs}
    clamp_post = _defined_risk_bounds(list(base_legs))
    out: list[float | None] = []
    for day in grid:
        value: float | None = 0.0
        for leg in base_legs:
            p = _price_asof({"k": series[id(leg)]}, "k", day, leg.expiration)
            if p is None:
                value = None
                break
            value += leg.qty * p
        if value is None:
            out.append(None)
            continue
        if b_day is None or day < b_day:
            p = _price_asof({"k": series[id(short_leg)]}, "k", day,
                            short_leg.expiration)
            if p is None:
                out.append(None)
                continue
            value += short_leg.qty * p
        else:
            if clamp_post is not None:
                value = max(clamp_post[0], min(clamp_post[1], value))
            value += short_leg.qty * b_cost
        out.append(value)
    return out


def f4_synth_trade(rec: dict, base_legs: list[Leg], short_leg: Leg,
                   entry_net: float, contracts: int,
                   buyback: tuple[date | None, float | None, str],
                   structure: str) -> Trade | None:
    """A frozen-harness `Trade` for the two-expiry F4 synthetic, or None.

    `bear_rewrap.synth_trade` with two deliberate differences, both forced by
    the second expiry:

      * MARKS come from `f4_net_marks` (segment-aware; clamped only after the
        buyback) rather than `net_marks` (one clamp over the whole path).
      * The LEG STRING carries the DEBIT legs ONLY. `Trade` rebuilds the path
        window from the leg string's NEAREST expiry, so handing it the short
        leg would truncate the debit's life to the short leg's — the opposite
        of the registered single-tranche construction, in which the position
        keeps running as a plain debit after the leg is closed. The short leg
        lives where the harness actually reads value: the marks. Nothing in
        this study reads `t.legs` afterwards — `_defined_risk_bounds` and
        `_max_loss_per_unit` are both called on the FULL leg list in `build()`,
        and no exit profile used here sets `und_buffer`, the only harness rule
        that touches `t.short_legs`.

    `contracts` is passed in rather than re-derived because the mgmt-$100
    trigger is quoted on the TRANCHE: the marks and the contract count have to
    be the same simulation, not two.
    """
    base_t: Trade = rec["t"]
    marks = f4_net_marks(base_legs, short_leg, base_t.grid, buyback)
    if all(m is None for m in marks):
        return None
    leg_str = "\n".join(
        f"{lg.ticker}:{lg.expiration.isoformat()}:{lg.strike:g}:"
        f"{'C' if lg.opt_type == 'Call' else 'P'} {lg.qty:+d}" for lg in base_legs)
    row = {
        "signal_date": base_t.signal_date.isoformat(),
        "ticker": base_t.ticker,
        "structure": structure,
        "entry_option_price": f"{entry_net:.4f}",
        "contracts": str(contracts),
        "dte_entry": str(base_t.dte_entry),
        "legs": leg_str,
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in marks),
    }
    try:
        return Trade(row)
    except (AssertionError, ValueError, KeyError):
        return None


# ── replay ───────────────────────────────────────────────────────────────────

def profile_for(rec: dict, entry_net: float) -> tuple[dict, str]:
    """`(exit profile, "debit"|"credit")`, assigned by the SIGN of the net entry.

    Debit-signed takes the shipped debit merge for the BASELINE row's regime
    cell (`prod_profile_for(rec, 0.50, True)` — base -> structure_exit ->
    regime_exit, the merge ARM P validated against the real book, including the
    bear-keyed `be_after 0.50` where the baseline carries it). Credit-signed
    takes `CREDIT_PROD`. `book.py`'s own convention is used for the sign:
    credit iff NOT entry_net > 0.
    """
    if entry_net > 0:
        return prod_profile_for(rec, 0.50, True), "debit"
    return dict(CREDIT_PROD), "credit"


def replay_at(t: Trade, prof: dict, contracts: int) -> dict:
    """Replay `t` at a given contract count. Contracts are not cosmetic: the
    harness's dollar_stop is an ABSOLUTE $1,000 cap read through `t.dollars`."""
    prev = t.contracts
    t.contracts = contracts
    try:
        out = replay(t, **prof)
        r = out["pnl_pct"]
        return dict(R=r, R_dol=t.dollars(r), exit_reason=out["exit_reason"],
                    days_held=out["days_held"], contracts=contracts)
    finally:
        t.contracts = prev


# ── build ────────────────────────────────────────────────────────────────────

def build(pop: list[tuple[dict, str]], shapes: tuple[str, ...]) -> dict:
    """Everything every gate and cell reads, built in one pass.

    Returns a dict with `baseline` rows, `cells` ({(shape, offset): [row]}),
    the G1 reconstruction census, the per-cell construction census, the clamp /
    sizing / flip / exposure tallies, and (when F4 is active) the fin_diag
    scrape-coverage census the AWAITING SCRAPE block reads.
    """
    g1: Counter = Counter()
    census: dict[tuple[str, int], Counter] = defaultdict(Counter)
    baseline: list[dict] = []
    cells: dict[tuple, list[dict]] = defaultdict(list)
    f4c: Counter = Counter()
    example: list = [None]          # the worked buyback example, first match wins

    active = [c for c in CELLS if c[0] in shapes]
    f4_active = any(c[0] == "F4" for c in active)

    for rec, dirn in pop:
        ok, why = BR.reconstructs(rec)
        g1[why] += 1
        if not ok:
            continue

        base_t: Trade = rec["t"]
        ed_base = BR.entry_date_for(base_t.legs, base_t.grid)
        base_prof, _ = profile_for(rec, base_t.entry_net)
        base_out = replay_at(base_t, base_prof, base_t.contracts)
        base_g = GK.entry_greeks(base_t.legs, ed_base) if ed_base else {}
        baseline.append(dict(
            date=rec["date"], ticker=rec["ticker"], structure=rec["structure"],
            source=rec["source"], tier=rec["tier"], mech_cell=rec["mech_cell"],
            dirn=dirn, mfe=rec["mfe"], mae=rec["mae"], key=id(rec), **base_out))
        base_row = baseline[-1]

        # One F4 plan per ROW, not per cell: both cells draw from the same
        # candidate set and only the delta pick differs, so the coverage census
        # and the two cells can never disagree about what the scrape owes.
        plan = None
        f4_pick: dict[int, tuple] = {}
        if f4_active:
            plan = f4_row_plan(rec, dirn, ed_base)
            f4c["rows"] += 1
            f4c[plan[3]] += 1
            if plan[0] is not None:
                f4c["candidates_wanted"] += DIAG_N_CANDIDATES
                f4c["candidates_cached"] += len(plan[1])

        for cell in active:
            shape, offset, mgmt = cell
            census[cell]["candidates"] += 1
            short_leg = None
            if shape == "F4":
                # Same rows across the three management cells (amendment 2:
                # "same underlying rows, no power cost per cell"), so the leg
                # pick is memoised per (row, |Delta| target) — `build_f4` reads
                # four candidates' greeks off disk and would otherwise repeat
                # that identically three times.
                if offset not in f4_pick:
                    f4_pick[offset] = build_f4(rec, plan, offset / 100.0, ed_base)
                legs, why_f4 = f4_pick[offset]
                if legs is None:
                    census[cell][why_f4] += 1
                    continue
                short_leg = legs[-1]
            else:
                legs = build_legs(rec, dirn, shape, offset)
                if legs is None:
                    census[cell]["skip_no_cached_ladder"] += 1
                    continue
            ed = BR.entry_date_for(legs, base_t.grid)
            if ed is None:
                census[cell]["skip_no_common_entry_day"] += 1
                continue
            if ed != ed_base:
                # Pre-registered: baseline and financed variant fill on the SAME
                # day or the row is excluded and counted.
                census[cell]["skip_entry_day_mismatch"] += 1
                continue
            net = BR.net_entry(legs, ed)
            if net is None:
                census[cell]["skip_entry_unpriced"] += 1
                continue
            if abs(net) < MIN_ABS_NET:
                census[cell]["skip_degenerate_premium"] += 1
                continue
            n_prod = unbounded = None
            credit = None
            buyback: tuple = (None, None, "")
            if shape == "F4":
                # The mgmt-$100 trigger is quoted on the TRANCHE, so the
                # contract count has to exist BEFORE the marks do; it is sized
                # off `net` here and reused for the replay so the marks and the
                # count are one simulation rather than two. F0-F3 keep sizing
                # off `t.entry_net` AFTER the fact: their cell means are
                # published and a 4-decimal CSV round-trip must not move them.
                n_prod, unbounded = size_contracts(net, legs)
                credit = f4_entry_credit(short_leg, ed)
                if credit is None or credit <= 0:
                    census[cell]["skip_credit_unpriced"] += 1
                    continue
                buyback = f4_buyback(short_leg, base_t.grid, ed, credit,
                                     n_prod, mgmt)
                t = f4_synth_trade(rec, legs[:-1], short_leg, net, n_prod,
                                   buyback, f"F4_d{offset}_{mgmt}")
            else:
                t = BR.synth_trade(rec, legs, f"{shape}_o{offset}")
            if t is None:
                census[cell]["skip_unpriceable_path"] += 1
                continue

            prof, sign = profile_for(rec, t.entry_net)
            if n_prod is None:
                n_prod, unbounded = size_contracts(t.entry_net, legs)
            out_prod = replay_at(t, prof, n_prod)
            out_fixed = replay_at(t, prof, base_t.contracts)
            pnls = [t.pnl_of(m) for m in t.marks if m is not None]
            g = GK.entry_greeks(legs, ed)

            census[cell]["built"] += 1
            census[cell][f"sign_{sign}"] += 1
            if unbounded:
                census[cell]["sizing_unbounded_fallback"] += 1

            # F4's segment bookkeeping: where the clamp boundary falls on the
            # path (now the BUYBACK session, amendment 2), what closed the leg
            # and at what cost, and whether it was still worth something at its
            # near expiry (the amendment-1 "forgiven value" count, kept for
            # comparability even though amendment 2 no longer forgives it).
            f4_extra: dict = {}
            if shape == "F4":
                b_day, b_cost, b_why = buyback
                n_pre = (len(base_t.grid) if b_day is None
                         else sum(1 for d in base_t.grid if d < b_day))
                last = f4_last_short_mark(short_leg)
                f4_extra = dict(
                    near_exp=short_leg.expiration, short_strike=short_leg.strike,
                    mgmt=mgmt, credit=credit, buyback_day=b_day,
                    buyback_cost=b_cost, buyback_why=b_why,
                    n_days_pre=n_pre, n_days_post=len(base_t.grid) - n_pre,
                    post_clamped=_defined_risk_bounds(legs[:-1]) is not None,
                    short_last_mark=last,
                    short_delta=GK.leg_greek(short_leg, ed, "Delta"))
                census[cell][f"why_{b_why}"] += 1
                if example[0] is None and mgmt != "hold" and \
                        b_why in ("pt50", "d100", "stop"):
                    example[0] = dict(
                        cell=cell, ticker=rec["ticker"], date=rec["date"],
                        entry_net=t.entry_net, credit=credit, contracts=n_prod,
                        buyback=buyback, base_legs=legs[:-1], short_leg=short_leg,
                        grid=base_t.grid, entry_day=ed)

            cells[cell].append(dict(
                date=rec["date"], ticker=rec["ticker"], structure=rec["structure"],
                source=rec["source"], tier=rec["tier"], mech_cell=rec["mech_cell"],
                dirn=dirn, key=id(rec), shape=shape, offset=offset,
                cell=cell,
                entry_net=t.entry_net, sign=sign, n_legs=len(legs),
                clamped=_defined_risk_bounds(legs) is not None,
                unbounded_size=unbounded,
                mfe=max(pnls) if pnls else None, mae=min(pnls) if pnls else None,
                base_R=base_row["R"], base_R_dol=base_row["R_dol"],
                base_contracts=base_t.contracts, base_net=base_t.entry_net,
                fixed_R=out_fixed["R"], fixed_R_dol=out_fixed["R_dol"],
                d_delta=(None if (g.get("delta") is None or base_g.get("delta") is None)
                         else g["delta"] - base_g["delta"]),
                d_abs_delta=(None if (g.get("delta") is None or base_g.get("delta") is None)
                             else abs(g["delta"]) - abs(base_g["delta"])),
                d_vega=(None if (g.get("vega") is None or base_g.get("vega") is None)
                        else g["vega"] - base_g["vega"]),
                base_delta=base_g.get("delta"), base_vega=base_g.get("vega"),
                **f4_extra, **out_prod))

    return dict(baseline=baseline, cells=dict(cells), g1=g1, census=dict(census),
                active=active, f4_census=f4c, f4_example=example[0])


# ── shared cell helpers ──────────────────────────────────────────────────────

def cell_label(cell: tuple[str, int, str]) -> str:
    shape, offset, mgmt = cell
    if shape == "F0":
        return f"{shape} own"          # degenerate offset axis (wording correction 2)
    if shape == "F4":
        # the |Delta| target (not a strike offset) x the management rule
        return f"F4-d{offset:02d} {MGMT_LABEL[mgmt].replace('mgmt-', '')}"
    return f"{shape} off{offset}"


def f4_awaiting(built: dict) -> bool:
    """True when F4 is active but NO cell built a single row — i.e. the
    fin_diag contracts are not in the cache yet. Distinct from underpowered:
    an underpowered cell has rows and too few dates; an awaiting cell has no
    contracts to price at all, and nothing about it is a finding."""
    f4 = [c for c in built["active"] if c[0] == "F4"]
    if not f4:
        return False
    return not any(built["cells"].get(c) for c in f4)


def n_dates(rows: list[dict]) -> int:
    return len({r["date"] for r in rows})


def powered(rows: list[dict]) -> bool:
    return len(rows) >= MIN_ROWS and n_dates(rows) >= MIN_DATES


def paired_rows(rows: list[dict], r_key: str = "R", b_key: str = "base_R") -> list[dict]:
    """Within-row pairs (financed, baseline) on rows BOTH variants price."""
    return [dict(date=r["date"], a=r[r_key], b=r[b_key], src=r["source"],
                 a_dol=r["R_dol"] if r_key == "R" else r["fixed_R_dol"],
                 b_dol=r["base_R_dol"])
            for r in rows if r.get(r_key) is not None and r.get(b_key) is not None]


def _mean(vals) -> float:
    vals = [v for v in vals if v is not None]
    return statistics.fmean(vals) if vals else float("nan")


def ex_both_cut(rows: list[dict]) -> list[dict]:
    """The ex-BOTH-dominant-windows cut, added BY HAND — `protocol.window_cuts`
    drops each window separately and an effect can survive both single cuts by
    living half in each."""
    months = set()
    for ms in P.DOMINANT_WINDOWS.values():
        months |= set(ms)
    return [r for r in rows if str(r["date"])[:7] not in months]


# ── G0 — POWER, prints FIRST ─────────────────────────────────────────────────

def gate_g0(built: dict, awaiting: bool = False) -> dict[tuple[str, int], bool]:
    hdr("G0 — POWER. Runs and prints FIRST; an underpowered cell is never read.")
    print(f"""  Pre-registered floor, declared before any cell was built:
  a shape x offset cell with < {MIN_DATES} dates OR < {MIN_ROWS} rows is
  UNDERPOWERED — its n is printed and NO criterion is evaluated on it. This
  is not a soft warning: an underpowered cell has no verdict other than
  UNDERPOWERED, and nothing below quotes its mean.""")
    print("""
  UNDERPOWERED reads as Amendment 1 worded it: too few dates to judge — the
  census is printed and nothing is concluded. Every shape prints that one
  token; reports published before 2026-08-22 say POWER-STOPPED and mean the
  same thing. AWAITING SCRAPE is neither: it means the contracts are not in
  the cache yet.""")
    print(f"\n  {'cell':<16} {'built':>7} {'dates':>7}  {'status':<16} shape")
    out: dict[tuple[str, int], bool] = {}
    seen: set[str] = set()
    for cell in built["active"]:
        rows = built["cells"].get(cell) or []
        ok = powered(rows)
        out[cell] = ok
        if cell[0] == "F4" and awaiting:
            status = "AWAITING SCRAPE"
        else:
            status = "POWERED" if ok else UNDERPOWERED
        desc = SHAPE_DESC[cell[0]] if cell[0] not in seen else ""
        seen.add(cell[0])
        print(f"  {cell_label(cell):<16} {len(rows):>7} {n_dates(rows):>7}  "
              f"{status:<16} {desc}")

    sub("constructibility census — why a candidate row did not become a cell row")
    for cell in built["active"]:
        c = built["census"].get(cell, Counter())
        parts = [f"{k[5:]}={v}" for k, v in sorted(c.items()) if k.startswith("skip_")]
        print(f"  {cell_label(cell):<16} candidates {c['candidates']:>4}  "
              f"built {c['built']:>4}   " + "  ".join(parts))
    return out


# ── F4 — the arm's scrape-coverage section ───────────────────────────────────

def report_f4(built: dict, awaiting: bool) -> None:
    """The F4 section: either the coverage census that lets the priced cells be
    read, or an explicit AWAITING SCRAPE block. Never a crash, never silently
    absent — an arm that quietly disappears from a report is how an unscraped
    cell gets mistaken for a null one."""
    hdr("F4 — DIAGONAL FINANCING (amendments 1-2): coverage + management")
    targets = "  ".join(f"{t:.2f}" for t in DIAG_TARGETS)
    mgmt_lines = "\n".join(f"    {MGMT_LABEL[m]:<10} {MGMT_DESC[m]}" for m in MGMT)
    c = built["f4_census"]
    print(f"""  F4 sells ONE short leg beyond the debit's outer strike at a NEARER expiry:
  the nearest cached expiry >= {DIAG_MIN_DAYS} calendar days after entry AND <= 1/2 the debit's
  DTE at entry, picked from the {DIAG_N_CANDIDATES} nearest cached strikes beyond by entry-day
  |Delta| closest to the cell's target ({targets}); off-target by more than
  {DIAG_DELTA_TOL:.2f} excludes the row (`target_unreachable`). Single tranche, never rolled.

  Those contracts sit at an expiry the BOOK never traded, so they are absent
  from the option-history cache until `scripts/collector/fetch_financing_legs.py`
  has fetched its `fin_diag_call` / `fin_diag_put` categories.

  MANAGEMENT (amendment 2) crosses each |Delta| target with three rules on the
  SAME rows, so the six cells cost no power against each other:
{mgmt_lines}
  Both mgmt bases also carry the loss stop: buy back at the first session whose
  mark >= {LOSS_MULT:.0f}x the entry credit. Neither profit base has precedence over the
  other (the staged_exit twin-cut precedent) — they report side by side.
  A leg still open at its near expiry is bought back at its LAST REAL MARK on
  EVERY cell, hold included: amendment 2 supersedes amendment 1's drop-to-zero,
  which forgave assignment.""")
    print(f"\n  rows planned                     {c['rows']:>6}")
    print(f"    no_near_expiry                 {c['skip_no_near_expiry']:>6}   "
          "(excluded and counted — registered)")
    print(f"    no common entry day            {c['skip_no_common_entry_day']:>6}")
    print(f"    near expiry, no cached strike  {c['skip_no_cached_candidate']:>6}")
    print(f"  candidate contracts wanted       {c['candidates_wanted']:>6}   "
          f"({DIAG_N_CANDIDATES} per row with a near expiry)")
    print(f"  candidate contracts cached       {c['candidates_cached']:>6}")
    for cell in built["active"]:
        if cell[0] != "F4":
            continue
        cc = built["census"].get(cell, Counter())
        print(f"  {cell_label(cell):<16} built {cc['built']:>4}   "
              f"target_unreachable {cc['skip_target_unreachable']:>4}   "
              f"greeks_absent {cc['skip_greeks_absent']:>4}   "
              f"no_entry_delta {cc['skip_no_entry_delta']:>4}")

    if awaiting:
        print(f"""
  AWAITING SCRAPE — fin_diag census: {c['candidates_cached']}/{c['candidates_wanted']} cached

  Every F4 cell below carries the verdict AWAITING SCRAPE: no rows, no mean, no
  CI, no criterion, and NOT a null. To fetch the legs (resumable, research
  tier, run by hand — this module never scrapes):

      python3 scripts/collector/fetch_financing_legs.py --dry-run
      python3 scripts/collector/fetch_financing_legs.py --limit 200""")
        return

    sub("what closed the financing leg — the management census")
    print(f"  {'cell':<16} {'n':>5} {'pt50':>6} {'$100':>6} {'stop':>6} "
          f"{'residual':>9} {'open':>6}  {'leg open':>9}  {'cost: mean':>10} "
          f"{'med':>6}")
    for cell in built["active"]:
        rows = built["cells"].get(cell) or []
        if cell[0] != "F4" or not rows:
            continue
        why = Counter(r["buyback_why"] for r in rows)
        costs = [r["buyback_cost"] for r in rows if r["buyback_cost"] is not None]
        print(f"  {cell_label(cell):<16} {len(rows):>5} {why['pt50']:>6} "
              f"{why['d100']:>6} {why['stop']:>6} "
              f"{why['residual_expiry'] + why['residual_no_mark']:>9} "
              f"{why['open_at_grid_end']:>6}  "
              f"{_mean([r['n_days_pre'] for r in rows]):>9.1f}  "
              f"{(_mean(costs) if costs else float('nan')):>10.3f} "
              f"{(statistics.median(costs) if costs else float('nan')):>6.3f}")
    print("""
  `leg open` = mean grid days the leg is live, which is where the SEGMENT
  BOUNDARY now falls: marks are UNCLAMPED while the leg is open (two expiries
  have no single-expiry arbitrage bound) and clamped afterwards, when the
  position is a plain debit carrying a fixed realized cost (G2's F4 clause).
  `residual` = never triggered, closed at the near expiry at its last real
  mark. `open` = the near expiry fell beyond the debit's 120-day path window,
  so the leg never closed inside the path.

  The entry session is excluded from every trigger scan (a build decision,
  stated not hidden): the credit IS that session's fill, so a trigger on the
  same day reads an Open-vs-mark spread rather than decay.""")

    rows = [r for cell in built["active"] if cell[0] == "F4"
            for r in (built["cells"].get(cell) or [])]
    if rows:
        live = [r for r in rows if r.get("short_last_mark") is not None
                and r["short_last_mark"] > FORGIVEN_MARK]
        print(f"""
  FORGIVEN-VALUE COUNT, kept for comparability with amendment 1's wording:
  {len(live)}/{len(rows)} cell-rows carried a last mark > ${FORGIVEN_MARK:.2f} into their near expiry.
  Under amendment 1 that value was dropped to zero and the model forgave an
  assignment real life would settle; under amendment 2 it is PAID as the
  residual buyback, so the count is now a disclosure of how much costing the
  change moved rather than of a forgiveness still in force.""")
    report_f4_example(built)


def report_f4_example(built: dict) -> None:
    """One worked buyback, printed day by day against its own hold counterpart.

    The algebra is asserted in `f4_net_marks`'s docstring; this prints a REAL
    row through it so the claim is auditable rather than argued. The two series
    are identical up to and including the buyback session — `C(b)` IS the
    buyback cost, so closing adds no discontinuity — and diverge only after,
    where the managed cell carries a frozen realized cost and the hold cell
    keeps marking a live leg."""
    ex = built.get("f4_example")
    if not ex:
        return
    b_day, b_cost, b_why = ex["buyback"]
    sub(f"worked buyback — {ex['ticker']} {ex['date']}  ({cell_label(ex['cell'])})")
    unit = abs(ex["short_leg"].qty)
    print(f"""  entry_net {ex['entry_net']:+.4f} = debit legs - {unit} x credit {ex['credit']:.4f}
  {ex['short_leg'].strike:g}{ex['short_leg'].opt_type[0]} exp {ex['short_leg'].expiration}   contracts {ex['contracts']}
  trigger {b_why} on {b_day} at a mark of {b_cost:.4f}""")
    managed = f4_net_marks(ex["base_legs"], ex["short_leg"], ex["grid"],
                           ex["buyback"])
    held = f4_net_marks(ex["base_legs"], ex["short_leg"], ex["grid"],
                        f4_buyback(ex["short_leg"], ex["grid"], ex["entry_day"],
                                   ex["credit"], ex["contracts"], "hold"))
    own = dict(BR.leg_series(ex["short_leg"]))
    idx = [i for i, d in enumerate(ex["grid"]) if d == b_day][0]
    lo, hi = max(0, idx - 2), min(len(ex["grid"]), idx + 4)
    print(f"\n  {'day':<12} {'leg mark':>9} {'managed net':>12} {'hold net':>10} "
          f"{'managed R':>10} {'hold R':>8}")
    net0 = ex["entry_net"]
    denom = abs(net0)

    def _f(v, w, spec):
        return ("-" if v is None else format(v, spec)).rjust(w)

    for i in range(lo, hi):
        d = ex["grid"][i]
        m, h = managed[i], held[i]
        mr = None if m is None else (m - net0) / denom
        hr = None if h is None else (h - net0) / denom
        tag = "  <- buyback" if d == b_day else ""
        print(f"  {str(d):<12} {_f(own.get(d), 9, '.4f')} {_f(m, 12, '+.4f')} "
              f"{_f(h, 10, '+.4f')} {_f(mr, 10, '+.3f')} {_f(hr, 8, '+.3f')}"
              + tag)
    qty = ex["short_leg"].qty
    realized = unit * (ex["credit"] - b_cost)
    print(f"""
  From the buyback session the managed net carries the CONSTANT
  {qty:+d} x {b_cost:.4f} = {qty * b_cost:+.4f} instead of the leg's live mark, so the
  leg's P&L is frozen at {unit} x ({ex['credit']:.4f} - {b_cost:.4f}) = {realized:+.4f} per unit
  and only the debit keeps moving. On the buyback session itself the two nets
  agree — C(b) IS the buyback cost, so closing adds no discontinuity.""")


# ── G1 — reconstruction ──────────────────────────────────────────────────────

def gate_g1(pop_n: int, g1: Counter) -> bool:
    hdr("G1 — RECONSTRUCTION. Can this code rebuild the rows it is about to wrap?")
    print("""  Every number below is a DIFFERENCE against a baseline replay. If the
  baseline cannot be rebuilt from the same cache by the same pricing code, that
  difference is measuring the re-pricer, not the wrapper. Tolerances are the
  pre-registered ones: entry +/-$0.005, per-day mark +/-$0.01, >= 95% of priced
  days agreeing. Failures are excluded from EVERY cell and counted by reason.""")
    ok = g1["ok"]
    print(f"\n  population rows            {pop_n:>5}")
    if pop_n:
        print(f"  reconstructed              {ok:>5}  ({ok / pop_n:.1%})")
    for reason, n in sorted(g1.items()):
        if reason != "ok":
            print(f"    failed: {reason:<26} {n:>5}")
    # G1 is a pass-rate report, not a run-killer: excluded rows are excluded, and
    # the rate is quoted so the rest of the page is readable. A zero pass rate is
    # the one state that makes everything downstream vacuous.
    passed = ok > 0
    print(f"\n  G1 {'PASS' if passed else 'FAIL'}"
          + ("" if passed else "  — nothing reconstructs; no cell is interpretable"))
    return passed


# ── G2 — clamp attribution ───────────────────────────────────────────────────

def gate_g2(built: dict) -> bool:
    hdr("G2 — CLAMP ATTRIBUTION. Does each shape's leg set have the risk it claims?")
    print("""  `_defined_risk_bounds` returns a clamp only for a structure whose payoff is
  bounded on BOTH sides at a single expiry. Registered expectation: F0/F1/F3 are
  defined-risk and must be ~100% clamped; F2 is the naked short and must be 100%
  UNclamped. A mismatch means the leg set is wrong and FAILS the run.

  DEVIATION FROM THE REGISTRATION, stated on the page rather than hidden in the
  arithmetic: F2's registered "100% unclamped" holds for a naked short CALL
  (bull base). A naked short PUT — F2 on a BEAR base — is structurally bounded
  at S=0, so `_defined_risk_bounds` clamps it CORRECTLY. That is geometry, not a
  build bug, so the gate is evaluated on the call-side subset and the put-side
  count is reported beside it. It is still an UNBOUNDED-in-practice short in the
  sizing sense only where `_max_loss_per_unit` says so (see G3).

  F4 (amendment 1) is judged on ITS OWN registered clause — "unclamped while
  the short leg lives". A diagonal spans two expirations, so
  `_defined_risk_bounds` correctly returns None for the whole leg set; the
  clamp is applied only AFTER the leg is closed, where the position is a plain
  single-expiry debit again carrying a fixed realized cost. Amendment 2 moves
  that boundary from the near expiry to the BUYBACK session, which on a managed
  cell is usually earlier; the counts and the mean boundary print below.""")
    ok = True
    print()
    for cell in built["active"]:
        rows = built["cells"].get(cell) or []
        if not rows:
            print(f"  {cell_label(cell):<16} no rows")
            continue
        shape = cell[0]
        n_clamped = sum(1 for r in rows if r["clamped"])
        share = n_clamped / len(rows)
        if shape == "F4":
            live_unclamped = sum(1 for r in rows if not r["clamped"])
            post = sum(1 for r in rows if r.get("post_clamped"))
            good = live_unclamped == len(rows)
            ok = ok and good
            print(f"  {cell_label(cell):<16} segment A (leg open) "
                  f"unclamped {live_unclamped:>4}/{len(rows):<4} -> "
                  f"{'PASS' if good else 'FAIL'}")
            print(f"  {'':<16} segment B (post-buyback, plain debit) "
                  f"clamped {post:>4}/{len(rows):<4}   boundary at a mean "
                  f"{_mean([r['n_days_pre'] for r in rows]):.1f} of "
                  f"{_mean([r['n_days_pre'] + r['n_days_post'] for r in rows]):.1f} "
                  "grid days")
        elif shape == "F2":
            call_side = [r for r in rows if r["dirn"] == "bull"]
            put_side = [r for r in rows if r["dirn"] == "bear"]
            bad = sum(1 for r in call_side if r["clamped"])
            good = bad == 0
            ok = ok and good
            print(f"  {cell_label(cell):<16} clamped {n_clamped:>4}/{len(rows):<4} "
                  f"({share:>5.1%})   naked-CALL subset {len(call_side)} rows, "
                  f"{bad} clamped -> {'PASS' if good else 'FAIL'}")
            print(f"  {'':<16} naked-PUT subset {len(put_side)} rows — bounded at "
                  f"S=0 by geometry, clamp is correct, NOT gated")
        else:
            good = share >= 0.99
            ok = ok and good
            print(f"  {cell_label(cell):<16} clamped {n_clamped:>4}/{len(rows):<4} "
                  f"({share:>5.1%})   expected ~100% -> {'PASS' if good else 'FAIL'}")
    print(f"\n  G2 {'PASS' if ok else 'FAIL'}")
    return ok


# ── G3 — sizing census ───────────────────────────────────────────────────────

def gate_g3(built: dict) -> None:
    hdr("G3 — SIZING CENSUS. The only place in this report that quotes dollars.")
    print("""  Contract counts differ by construction: a wrapper changes the premium, and
  the production formula re-sizes on it. That is why every comparison below this
  section is quoted in R and never in $ — and why the `--fixed-contracts`
  control exists. Sizing branches are `simulate.py::_size_contracts` verbatim:
  debit on premium x 100 x 0.75, credit on structural max loss x 100, unbounded
  credit at 1 contract.""")
    print(f"\n  {'cell':<16} {'n':>5} {'contracts: mean':>16} {'med':>5} "
          f"{'min':>5} {'max':>5} {'=1':>6} {'unbnd':>6}  {'baseline mean':>13} "
          f"{'total $':>12}")
    base = built["baseline"]
    if base:
        bc = [r["contracts"] for r in base]
        print(f"  {'BASELINE':<10} {len(base):>5} {statistics.fmean(bc):>16.2f} "
              f"{statistics.median(bc):>5.0f} {min(bc):>5} {max(bc):>5} "
              f"{sum(1 for c in bc if c == 1):>6} {'—':>6}  {'—':>13} "
              f"{sum(r['R_dol'] for r in base):>12,.0f}")
    for cell in built["active"]:
        rows = built["cells"].get(cell) or []
        if not rows:
            if cell[0] == "F4":
                print(f"  {cell_label(cell):<16} {0:>5}   no rows — AWAITING SCRAPE")
            continue
        cs = [r["contracts"] for r in rows]
        bcs = [r["base_contracts"] for r in rows]
        print(f"  {cell_label(cell):<16} {len(rows):>5} {statistics.fmean(cs):>16.2f} "
              f"{statistics.median(cs):>5.0f} {min(cs):>5} {max(cs):>5} "
              f"{sum(1 for c in cs if c == 1):>6} "
              f"{sum(1 for r in rows if r['unbounded_size']):>6}  "
              f"{statistics.fmean(bcs):>13.2f} "
              f"{sum(r['R_dol'] for r in rows):>12,.0f}")
    print("\n  `unbnd` = rows that took the 1-contract unbounded-credit fallback.")


# ── the debit/credit flip, read BEFORE any dR ────────────────────────────────

def report_flip(built: dict) -> None:
    hdr("EXIT ASSIGNMENT — the debit/credit flip share, per shape")
    print("""  Exits are assigned by the SIGN of the synthetic net entry: debit-signed
  replays the shipped debit merge, credit-signed replays CREDIT_PROD. A shape
  that flips a large share of its rows to the credit profile has changed the
  EXIT RULE as well as the wrapper, and its dR is not a pure structure read.
  This is printed before any dR on purpose.""")
    print(f"\n  {'cell':<16} {'n':>5} {'debit':>7} {'credit':>7} {'flip share':>11}"
          f"  {'mean net':>9}  {'baseline net':>13}")
    for cell in built["active"]:
        rows = built["cells"].get(cell) or []
        if not rows:
            if cell[0] == "F4":
                print(f"  {cell_label(cell):<16} {0:>5}   no rows — AWAITING SCRAPE")
            continue
        nd = sum(1 for r in rows if r["sign"] == "debit")
        nc = len(rows) - nd
        print(f"  {cell_label(cell):<16} {len(rows):>5} {nd:>7} {nc:>7} "
              f"{nc / len(rows):>10.1%}  {_mean([r['entry_net'] for r in rows]):>+9.3f}"
              f"  {_mean([r['base_net'] for r in rows]):>+13.3f}")


# ── cells ────────────────────────────────────────────────────────────────────

def report_cells(built: dict, power: dict, awaiting: bool = False) -> None:
    hdr("CELLS — paired dR (financed minus baseline), R only, never dollars")
    print("""  Unit is the signal DATE: every CI resamples dates, not rows. The pair is
  within-row on rows BOTH variants price. `gb` = |mean MAE| / mean MFE, `cap` =
  mean R / mean MFE, both recomputed off the synthetic's OWN path (a wrapper
  walks a different path, so the baseline's stored MFE/MAE do not describe it).""")
    print()
    base = built["baseline"]
    if base:
        print(fmt_row("baseline", cell_stats(base), width=12))

    for cell in built["active"]:
        rows = built["cells"].get(cell) or []
        if not rows:
            if cell[0] == "F4":
                sub(f"{cell_label(cell)} — "
                    + ("AWAITING SCRAPE" if awaiting else "no rows built"))
                print("  No rows: the fin_diag legs are not cached yet. No mean, "
                      "no CI, no criterion,\n  and NOT a null result.")
            continue
        if not power[cell]:
            sub(f"{cell_label(cell)} — {UNDERPOWERED}")
            print(f"  n={len(rows)} rows / {n_dates(rows)} dates "
                  f"(floor {MIN_ROWS} rows / {MIN_DATES} dates). "
                  "No mean, no CI, no criterion.")
            continue
        sub(f"{cell_label(cell)} — {SHAPE_DESC[cell[0]]}")
        print(fmt_row("financed", cell_stats(rows), width=12))
        pr = paired_rows(rows)
        if not pr:
            print("  no paired rows")
            continue
        d_mean = _mean([p["a"] - p["b"] for p in pr])
        lo, hi = P.boot_ci_paired_by_date(pr, "a", "b")
        print(f"  PROD-SIZED   n={len(pr):>4} / {n_dates(pr):>3} dates   "
              f"dR {d_mean:+.3f}   CI [{lo:+.3f}, {hi:+.3f}]")
        mean_g, share, min_g, folds = P.loo_by_date(pr, lambda r: r["a"],
                                                    lambda r: r["b"])
        print(f"  LOO-by-date  mean {mean_g:+.3f}  share+ {share:.0%}  "
              f"MIN {min_g:+.3f}  ({folds} folds)")
        for cut, rs in P.window_cuts(pr).items():
            if rs:
                print(f"    {cut:<16} n={len(rs):>4}  "
                      f"dR {_mean([r['a'] - r['b'] for r in rs]):+.3f}")
        exb = ex_both_cut(pr)
        if exb:
            print(f"    {'ex_BOTH':<16} n={len(exb):>4}  "
                  f"dR {_mean([r['a'] - r['b'] for r in exb]):+.3f}   (by hand)")
        years = {y: _mean([r["a"] - r["b"] for r in rs])
                 for y, rs in P.by_year(pr).items()}
        print("    by year: " + "  ".join(f"{y} {v:+.3f}" for y, v in years.items()))

        fx = paired_rows(rows, r_key="fixed_R")
        if fx:
            flo, fhi = P.boot_ci_paired_by_date(fx, "a", "b")
            print(f"  FIXED-CONTRACTS control (contracts held at the baseline's "
                  f"count)\n    n={len(fx):>4}   "
                  f"dR {_mean([p['a'] - p['b'] for p in fx]):+.3f}   "
                  f"CI [{flo:+.3f}, {fhi:+.3f}]")
        mix = Counter(r["exit_reason"] for r in rows)
        print("    exits: " + "  ".join(f"{k}={v}" for k, v in mix.most_common()))


# ── E1 / E2 — exposure ───────────────────────────────────────────────────────

def report_e1_e2(built: dict) -> bool:
    hdr("E1 / E2 — EXPOSURE. What the wrapper actually did to delta and vega.")
    print("""  Per-leg greeks read from the same cached history CSVs the pricing reads
  (lib/greeks.py: signed, qty-scaled, ALL-OR-NOTHING per greek — a missing leg
  makes the greek None, never 0).

  E1 is a GATE, not a finding. The geometry is deterministic: F1 (a credit
  spread against the debit's direction) MUST reduce |net delta|; F0 and F3 add
  same-direction premium and MUST increase it. A shape whose delta does not move
  as its geometry dictates is a BUILD BUG and fails the run. F2's direction is
  reported, not gated — the registration pins F1 and F0/F3 only, and amendment
  1 pins F4: a short leg sold against the debit's own direction MUST reduce
  |net delta|.

  E2 is descriptive: every financing shape sells an extra option and is
  structurally short vega. This quantifies it; nothing is gated on it.""")
    print(f"\n  {'cell':<16} {'n':>5} {'base delta':>11} {'d(net delta)':>13} "
          f"{'d|net delta|':>13} {'row-sign ok':>12}  {'d(net vega)':>12} "
          f"{'base vega':>10}")
    ok = True
    for cell in built["active"]:
        rows = built["cells"].get(cell) or []
        have = [r for r in rows if r["d_abs_delta"] is not None]
        if not have:
            note = ("no rows — AWAITING SCRAPE" if (not rows and cell[0] == "F4")
                    else "greeks unavailable on every row")
            print(f"  {cell_label(cell):<16} {note}")
            continue
        m_abs = _mean([r["d_abs_delta"] for r in have])
        expect = E1_EXPECT.get(cell[0])
        if expect is None:
            verdict = "n/a (F2)"
        else:
            good = (m_abs > 0) if expect > 0 else (m_abs < 0)
            ok = ok and good
            per_row = sum(1 for r in have
                          if (r["d_abs_delta"] > 0) == (expect > 0)) / len(have)
            verdict = f"{'PASS' if good else 'FAIL'} {per_row:.0%}"
        vg = [r["d_vega"] for r in have if r["d_vega"] is not None]
        print(f"  {cell_label(cell):<16} {len(have):>5} "
              f"{_mean([r['base_delta'] for r in have]):>+11.3f} "
              f"{_mean([r['d_delta'] for r in have]):>+13.3f} "
              f"{m_abs:>+13.3f} {verdict:>12}  "
              f"{(_mean(vg) if vg else float('nan')):>+12.3f} "
              f"{_mean([r['base_vega'] for r in have]):>+10.3f}")
    print("\n  `row-sign ok` = share of rows whose |delta| moved the registered "
          "way (diagnostic;\n  the gate is on the MEAN, which is what the "
          "registration pins).")
    print(f"\n  E1 {'PASS' if ok else 'FAIL'}")
    return ok


# ── E3 — correlation with the deployed sleeve ────────────────────────────────

def sleeve_daily(recs: list[dict]) -> dict[str, float]:
    """Mean R per date of the DEPLOYED ladder — `top_k_per_day(ladder_rank, k=3)`,
    the same join `bear_rewrap`'s ARM P / P2 makes."""
    ladder = P.top_k_per_day(recs, P.ladder_rank, k=3, eligible_fn=P.ladder_eligible)
    by: dict[str, list[float]] = defaultdict(list)
    for r in ladder:
        if r.get("R") is not None:
            by[str(r["date"])].append(float(r["R"]))
    return {d: statistics.fmean(v) for d, v in by.items() if v}


def cell_corr(rows: list[dict], sleeve: dict[str, float],
              r_key: str = "R") -> tuple[float | None, int]:
    """`(corr, n_shared_dates)` of the cell's daily mean R vs the sleeve's."""
    shared = sorted({r["date"] for r in rows} & set(sleeve))
    pts = [(sleeve[d], _mean([r[r_key] for r in rows if r["date"] == d]))
           for d in shared]
    pts = [(a, b) for a, b in pts if b == b]
    if len(pts) < MIN_SHARED_DATES:
        return None, len(pts)
    try:
        return statistics.correlation([a for a, _ in pts], [b for _, b in pts]), len(pts)
    except statistics.StatisticsError:
        return None, len(pts)


def report_e3(built: dict, power: dict, sleeve: dict[str, float]) -> dict:
    hdr("E3 — CORRELATION WITH THE DEPLOYED SLEEVE (the vol_sleeve lesson)")
    print(f"""  The deployed sleeve is `top_k_per_day(ladder_rank, k=3)` over the eligible
  book — {len(sleeve)} dates. These shapes are synthesized on the ENGINE'S OWN
  signal dates, so a wrapper can clear every R gate and still be re-wrapping the
  SAME exposure. Registered reading, fixed before the run:

      POSITIVE correlation = RE-WRAP verdict, REGARDLESS of dR.

  >= {MIN_SHARED_DATES} shared dates required; per year alongside.""")
    out: dict[tuple[str, int], tuple[float | None, int]] = {}
    print(f"\n  {'cell':<16} {'corr':>8} {'dates':>7}   by year")
    for cell in built["active"]:
        rows = built["cells"].get(cell) or []
        if not rows:
            if cell[0] == "F4":
                print(f"  {cell_label(cell):<16} {'n/a':>8} {0:>7}   AWAITING SCRAPE")
            continue
        corr, n = cell_corr(rows, sleeve)
        out[cell] = (corr, n)
        parts = []
        for y, rs in P.by_year(rows).items():
            c, _ = cell_corr(rs, sleeve)
            if c is not None:
                parts.append(f"{y} {c:+.3f}")
        flag = ("" if power[cell]
                else f"  ({UNDERPOWERED} — not read)")
        cs = f"{corr:>+8.3f}" if corr is not None else f"{'n/a':>8}"
        print(f"  {cell_label(cell):<16} {cs} {n:>7}   " + "  ".join(parts) + flag)
    return out


# ── criteria + verdicts ──────────────────────────────────────────────────────

def evaluate(cell: tuple[str, int], rows: list[dict], powered_ok: bool,
             e3: tuple[float | None, int] | None,
             r_key: str = "R",
             awaiting: bool = False) -> tuple[str, list[tuple[str, bool | None, str]]]:
    """`(verdict, [(criterion, pass|None, detail)])` — the full conjunction."""
    if awaiting and cell[0] == "F4" and not rows:
        return "AWAITING SCRAPE", []
    if not powered_ok or not rows:
        return UNDERPOWERED, []
    pr = paired_rows(rows, r_key=r_key)
    if not pr:
        return UNDERPOWERED, []

    checks: list[tuple[str, bool | None, str]] = []

    d_mean = _mean([p["a"] - p["b"] for p in pr])
    lo, hi = P.boot_ci_paired_by_date(pr, "a", "b")
    c1 = d_mean > 0 and lo > 0
    checks.append(("1 paired dR > 0, CI excludes zero", c1,
                   f"dR {d_mean:+.3f}  CI [{lo:+.3f}, {hi:+.3f}]"))

    _, share, min_g, folds = P.loo_by_date(pr, lambda r: r["a"], lambda r: r["b"])
    c2 = min_g == min_g and min_g > 0
    checks.append(("2 every LOO fold positive", c2,
                   f"MIN {min_g:+.3f} over {folds} folds (share+ {share:.0%})"))

    cuts = {k: _mean([r["a"] - r["b"] for r in rs])
            for k, rs in P.window_cuts(pr).items() if rs and k != "ALL"}
    exb = ex_both_cut(pr)
    if exb:
        cuts["ex_BOTH"] = _mean([r["a"] - r["b"] for r in exb])
    c3 = bool(cuts) and all(v > 0 for v in cuts.values())
    checks.append(("3 window cuts + ex-BOTH", c3,
                   "  ".join(f"{k} {v:+.3f}" for k, v in cuts.items())))

    years = {y: _mean([r["a"] - r["b"] for r in rs]) for y, rs in P.by_year(pr).items()}
    c4 = bool(years) and all(v > 0 for v in years.values())
    checks.append(("4 sign-stable every year", c4,
                   "  ".join(f"{y} {v:+.3f}" for y, v in years.items())))

    tiers = {}
    for src in ("real", "tweak"):
        rs = [p for p in pr if p["src"] == src]
        if rs:
            tiers[src] = (_mean([p["a"] - p["b"] for p in rs]), len(rs))
    c5 = bool(tiers) and all(v[0] > 0 for v in tiers.values())
    checks.append(("5 right-signed both pricing tiers", c5,
                   "  ".join(f"{k} n={v[1]} dR {v[0]:+.3f}" for k, v in tiers.items())))

    nd = n_dates(pr)
    c6 = nd >= MIN_DATES
    checks.append((f"6 >= {MIN_DATES} affected dates (priced set)", c6, f"{nd} dates"))

    corr, n_shared = e3 if e3 else (None, 0)
    if corr is None:
        c7: bool | None = None
        detail = f"NOT EVALUABLE — {n_shared} shared dates (< {MIN_SHARED_DATES})"
    else:
        c7 = corr <= 0
        detail = f"corr {corr:+.3f} over {n_shared} shared dates"
    checks.append(("7 E3 <= 0 (does not re-wrap the sleeve)", c7, detail))

    r_gates = [c1, c2, c3, c4, c5, c6]
    if all(r_gates) and c7 is True:
        return "CANDIDATE", checks
    if all(r_gates) and c7 is False:
        return "RE-WRAP", checks
    return "NULL", checks


def report_criteria(built: dict, power: dict, e3: dict, r_key: str = "R",
                    title: str = "",
                    awaiting: bool = False) -> dict[tuple[str, int], str]:
    hdr("CRITERIA — the pre-registered conjunction, per shape x offset" + title)
    print("""  All seven or nothing. Failing any one is failing; there is no partial
  credit and no "promising" cell. CANDIDATE is NOT a ship — it queues an
  independent-window confirmation, and nothing ships from a research-tier study.

    CANDIDATE      clears 1-7
    RE-WRAP        clears 1-6, fails 7 — the financing does not diversify
    NULL           clears the CI but fails LOO / ex-BOTH / sign stability, or
                   never cleared it — window artifact, recorded
    UNDERPOWERED   G0 floored the cell — too few dates to judge; the census is
                   published, nothing is concluded, and there is no re-run
    AWAITING SCRAPE  the cell's contracts are not cached yet. Not a null, not
                   an underpowered cell: nothing was priced at all.""")
    verdicts: dict[tuple[str, int], str] = {}
    for cell in built["active"]:
        rows = built["cells"].get(cell) or []
        verdict, checks = evaluate(cell, rows, power.get(cell, False),
                                   e3.get(cell), r_key=r_key, awaiting=awaiting)
        verdicts[cell] = verdict
        sub(f"{cell_label(cell)}  —  {verdict}")
        if not checks:
            if verdict == "AWAITING SCRAPE":
                print("  n=0 rows — the fin_diag legs are not cached yet. No "
                      "criterion evaluated,\n  and no verdict may be read off "
                      "this cell in either direction.")
            else:
                print(f"  n={len(rows)} rows / {n_dates(rows)} dates — under the "
                      "G0 floor, no criterion evaluated.")
            continue
        for name, ok, detail in checks:
            mark = "PASS" if ok is True else ("FAIL" if ok is False else " ?? ")
            print(f"  [{mark}] {name:<40} {detail}")
    return verdicts


# ── descriptive, NOT criteria ────────────────────────────────────────────────

def report_descriptive(built: dict, power: dict, sleeve: dict[str, float]) -> None:
    hdr("DESCRIPTIVE — worst-decile behaviour. NOT A CRITERION.")
    print("""  NOT A CRITERION. Printed because a hedge question always gets asked, and
  refused as evidence because 118 dates cannot power a worst-decile read — the
  decile is ~12 dates and the 2026-08-13 hedge-programme wall is exactly this
  mistake. No verdict above depends on anything in this block, and no cell may
  be promoted on it.""")
    if not sleeve:
        print("\n  no deployed sleeve — nothing to cut on")
        return
    vals = sorted(sleeve.values())
    cutoff = vals[max(0, len(vals) // 10 - 1)]
    worst = {d for d, v in sleeve.items() if v <= cutoff}
    print(f"\n  deployed sleeve {len(sleeve)} dates; worst decile = {len(worst)} "
          f"dates (mean R <= {cutoff:+.3f})")
    base_worst = [r for r in built["baseline"] if r["date"] in worst]
    if base_worst:
        print(f"  {'baseline':<16} n={len(base_worst):>4}  "
              f"meanR {_mean([r['R'] for r in base_worst]):+.3f}")
    for cell in built["active"]:
        rows = [r for r in (built["cells"].get(cell) or []) if r["date"] in worst]
        if not rows:
            continue
        tag = "" if power[cell] else "  (cell UNDERPOWERED)"
        print(f"  {cell_label(cell):<16} n={len(rows):>4}  "
              f"meanR {_mean([r['R'] for r in rows]):+.3f}  "
              f"dR {_mean([r['R'] - r['base_R'] for r in rows]):+.3f}"
              f"   NOT A CRITERION{tag}")


# ── header ───────────────────────────────────────────────────────────────────

def report_header(recs: list[dict], diag: dict, pop: list, why: Counter,
                  n_full: int) -> None:
    hdr("financed_spread — does financing a book debit vertical improve it?")
    print(f"  era {diag['era']}   book {len(recs)} rows / {diag['n_dates']} dates   "
          f"{diag['date_range'][0]} .. {diag['date_range'][1]}")
    print("  by source: " + "  ".join(
        f"{k}={v}" for k, v in sorted(Counter(r["source"] for r in recs).items())))
    dc = diag["debit_calib"]
    print(f"  debit_calib      n={dc['n']}  exact={dc['exact']}  "
          f"near-rounding-tie={dc['near']}  hard={dc['hard']}")
    print(f"  n_credit_ungated {diag['n_credit_ungated']}   (credit rows are "
          "admitted WITHOUT the exact-replay\n                   calibration gate — "
          "see lib/book.py's docstring; a credit-signed\n                   "
          "synthetic here is replayed by this code, not read from the book)")
    print(f"  proxy debit rows excluded (non-exact) "
          f"{diag['n_proxy_excluded_non_exact']}")
    if diag.get("mech_table_warning"):
        print(f"  WARNING: {diag['mech_table_warning']}")

    sub("population — two-leg single-expiry DEBIT verticals")
    print(f"  kept {n_full}  (bull {why['kept_bull']} / bear {why['kept_bear']})"
          f"   of {why['book_rows']} book rows")
    if len(pop) != n_full:
        print(f"  *** BUILD-ONLY --limit-rows: only the first {len(pop)} of those "
              "are built. NOT the study.")
    for k, v in sorted(why.items()):
        if k.startswith("excl_"):
            print(f"    excluded: {k[5:]:<26} {v:>5}")
    print("\n  Population is read off the LEG GEOMETRY, not off the `structure` "
          "label:\n  the label is a classifier output and the strike ladder is not.")


# ── main ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arms", default="CEKD",
                    help="report sections: C cells, E exposure, K criteria, "
                         "D descriptive. Gates G0-G3 always run.")
    ap.add_argument("--shapes", default=",".join(SHAPES),
                    help="BUILD-ONLY dev flag: comma-separated subset of "
                         "F0,F1,F2,F3,F4. A partial run is NOT the study.")
    ap.add_argument("--limit-rows", type=int, default=0,
                    help="BUILD-ONLY dev flag: cap the population at N rows for "
                         "a smoke run. A capped run is NOT the study.")
    ap.add_argument("--fixed-contracts", action="store_true",
                    help="ALSO run the full criteria conjunction on the "
                         "fixed-contracts control as a labelled SENSITIVITY. "
                         "The control's dR and CI are printed in CELLS either "
                         "way; the pre-registered primary is production "
                         "re-sizing per variant, and a sensitivity may not "
                         "change a verdict.")
    a = ap.parse_args(argv)

    shapes = tuple(s.strip().upper() for s in a.shapes.split(",") if s.strip())
    bad = [s for s in shapes if s not in SHAPES]
    if bad:
        print(f"unknown shape(s): {bad}", file=sys.stderr)
        return EXIT_GATE_FAILED

    # load_book owns the era guard: it refuses exit 3 when the exports on disk
    # are not the era asked for, and exit 2 when the era is too thin to conclude
    # from. Both are DESIGNED refusals (declared above), not failures.
    recs, diag = load_book(include_bs=False)

    pop, why = population(recs)
    n_full = len(pop)
    if a.limit_rows:
        pop = pop[:a.limit_rows]

    partial = bool(a.limit_rows) or set(shapes) != set(SHAPES)
    if partial:
        print("=" * 78)
        print("*** PARTIAL RUN — BUILD-ONLY FLAGS IN USE. THIS IS NOT THE STUDY. ***")
        print(f"***   shapes={','.join(shapes)}  limit_rows={a.limit_rows or 'none'}")
        print("***   Every shape x offset cell is reported in the real run, "
              "regardless of outcome.")
        print("=" * 78)

    report_header(recs, diag, pop, why, n_full)

    built = build(pop, shapes)

    # G0 RUNS AND PRINTS FIRST — the registration's "runs FIRST", in execution
    # order as well as on the page.
    awaiting = f4_awaiting(built)
    power = gate_g0(built, awaiting)
    if any(c[0] == "F4" for c in built["active"]):
        report_f4(built, awaiting)
    ok_g1 = gate_g1(len(pop), built["g1"])
    ok_g2 = gate_g2(built)
    gate_g3(built)

    report_flip(built)

    sleeve = sleeve_daily(recs)
    if "C" in a.arms:
        report_cells(built, power, awaiting)
    ok_e1 = report_e1_e2(built) if "E" in a.arms or "K" in a.arms else True
    e3 = report_e3(built, power, sleeve) if "E" in a.arms or "K" in a.arms else {}

    verdicts: dict[tuple[str, int], str] = {}
    if "K" in a.arms:
        verdicts = report_criteria(built, power, e3, awaiting=awaiting)
        if a.fixed_contracts:
            e3_fx = {cell: cell_corr(built["cells"].get(cell) or [], sleeve,
                                     r_key="fixed_R")
                     for cell in built["active"]}
            report_criteria(built, power, e3_fx, r_key="fixed_R",
                            title="  —  FIXED-CONTRACTS SENSITIVITY",
                            awaiting=awaiting)
            print("\n  SENSITIVITY ONLY. The pre-registered primary is "
                  "production re-sizing per\n  variant; nothing above changes a "
                  "verdict in the VERDICTS block below.")
    if "D" in a.arms:
        report_descriptive(built, power, sleeve)

    if verdicts:
        hdr("VERDICTS")
        for cell in built["active"]:
            default = ("AWAITING SCRAPE" if (cell[0] == "F4" and awaiting)
                       else UNDERPOWERED)
            print(f"  {cell_label(cell):<16} {verdicts.get(cell, default)}")
        print("\n  CANDIDATE is not a ship. Nothing ships from a research-tier "
              "study.")

    failed = [name for name, ok in
              (("G1 reconstruction", ok_g1), ("G2 clamp attribution", ok_g2),
               ("E1 delta geometry", ok_e1)) if not ok]
    if failed:
        hdr("RUN FAILED")
        print("  " + "; ".join(failed))
        print("  A failed gate is a BUILD BUG, not a finding — nothing above is "
              "readable as evidence.")
        return EXIT_GATE_FAILED
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
