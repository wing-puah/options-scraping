"""Hedge INSTRUMENT selection and pricing for the `hedge_exposure` study.

Implements the instrument half of
`research/pre-registrations/f4_deployment/hedge_exposure.md`:

  * §"Fill coverage, per proxy" + gate **G-FILL** — the two committed fill
    rules and the coverage report the gate is read from.
  * **ARM C / ARM CS / ARM P** — the proxy PUT, band rule primary and
    nearest-available as the registered sensitivity.
  * **ARM R** — the always-fillable delta-equivalent SHORT in the proxy
    UNDERLYING.

It argues nothing. Which sessions are triggered, how the hedge is sized, and
what the drawdown curve does with it all live in the study module; this file
only answers "what would you buy, and what was it worth each day".

THE TWO COMMITTED RULES
-----------------------
Both are fixed in the pre-registration and may not be edited here:

  BAND (primary)      expiry 25–75 DTE, strike within ±5% of that session's
                      close, and a usable price on the session itself.
  NEAREST-AVAILABLE   nearest quoted strike AT-OR-BELOW spot, at the expiry
   (sensitivity)      nearest 45 DTE within a 20–120 DTE window.

WHAT COUNTS AS FILLABLE
-----------------------
`lib/barchart/options.py::_mark` — mid(Bid,Ask) when both are > 0, else Latest
when > 0. A contract with no mark on the session is NOT fillable, and this
module returns **None** rather than a fabricated fill. Per the pre-registration
those sessions are carried by the study at f=0 and counted AGAINST the fill
gate, never dropped from the population (`calendar_hedge`'s standing rule that
a hedge unavailable exactly when needed is not a hedge).

THE INSTRUMENT EXCLUSION IS A FUNCTION CALL, NOT A NAME LIST
------------------------------------------------------------
`underlying.rescaled_tickers()` names the tickers whose scraped bars sit on a
split-adjusted basis, so their absolute dollar moves are not comparable with
the book's unadjusted prices. Anything on that list is refused as an
instrument, for the put arms and for ARM R alike. XLE falls out this way; it is
NOT special-cased by name, so if the rescale list changes the exclusion moves
with it.

DUPLICATED, NOT IMPORTED
------------------------
`_put_index()` re-implements the option-cache filename convention that
`f3_structure/vol_sleeve.py::_strike_index` encodes (`TICKER_YYYYMMDD_STRIKE[C|P].csv`,
expiry and strike parsed off the stem). Per the `lib/` layering rule stated in
`greeks.py`, a module here MUST NOT import from a study folder (`f1_*`…`f4_*`),
so the convention is restated rather than imported — the same trade `greeks.py`
makes for `bear_rewrap.entry_date_for`. It is indexed per TICKER and lazily,
because a hedge only ever looks at the ~11 proxies.

Carry-forward pricing mirrors `scripts/backtest/helpers.py::_price_asof` (most
recent mark on or before the day, never past expiry), which is what
`bear_rewrap.net_marks` and production both do.

THE FROZEN HARNESS
------------------
`harness.py` is FROZEN and is used here only as the per-position primitive, the
way `account_sim` and `vol_sleeve` use it: `harness_trade()` packs a picked put
into a synthetic row and hands it to the frozen `Trade`, so a caller that wants
exit replay gets byte-identical exit logic. Nothing in this module edits it,
and the mark-to-market path (`price_path`) does not go through it at all —
a mark-to-market carry has no exit scan to replay.

Read-only: touches no config, writes no tab, scrapes nothing.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.barchart.options import cache_path, parse_history_details  # noqa: E402
from scripts.backtest.config import HISTORY_CACHE  # noqa: E402
from scripts.backtest.helpers import _weekday_grid  # noqa: E402
from scripts.backtest.legs import Leg  # noqa: E402
from scripts.backtest_study.lib import greeks as G  # noqa: E402
from scripts.backtest_study.lib import underlying as U  # noqa: E402
from scripts.backtest_study.lib.harness import PATH_CAP_DAYS, Trade  # noqa: E402

# ── committed constants (pre-registration; NOT tunable here) ─────────────────

BAND_DTE_LO, BAND_DTE_HI = 25, 75          # band rule expiry window
BAND_STRIKE_PCT = 0.05                     # band rule strike window, ±5% of close
NEAREST_DTE_LO, NEAREST_DTE_HI = 20, 120   # nearest-available expiry window
NEAREST_ANCHOR_DTE = 45                    # nearest-available expiry anchor
FILL_GATE = 0.60                           # G-FILL: band-rule fills / triggered sessions

RULE_BAND = "band"
RULE_NEAREST = "nearest"
RULES = (RULE_BAND, RULE_NEAREST)

SHARES_PER_CONTRACT = 100

# Why a pick failed. Reported, never silently pooled: "this proxy is withheld"
# and "nothing quoted that day" are different facts about the market.
NO_SPOT = "no_spot"
RESCALED = "instrument_rescaled"
NO_CONTRACT = "no_contract_in_rule"
NO_MARK = "no_usable_price"
BAD_RULE = "unknown_rule"
FILLED = "filled"


# ── the option cache, per ticker ─────────────────────────────────────────────

@lru_cache(maxsize=None)
def _put_index(ticker: str) -> dict[date, tuple[float, ...]]:
    """`{expiry: (strike, ...)}` over the cached PUTs of one ticker, ascending.

    Filename convention `TICKER_YYYYMMDD_STRIKE[C|P].csv`, as
    `vol_sleeve._strike_index` encodes it (restated, not imported — see the
    module docstring).
    """
    ticker = ticker.upper().strip()
    out: dict[date, list[float]] = {}
    if not HISTORY_CACHE.exists():
        return {}
    for path in HISTORY_CACHE.glob(f"{ticker}_*P.csv"):
        parts = path.stem.split("_")
        if len(parts) != 3:
            continue
        tk, stamp, tail = parts
        if tk != ticker or not tail.endswith("P"):
            continue
        try:
            exp = date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))
            strike = float(tail[:-1])
        except (ValueError, IndexError):
            continue
        out.setdefault(exp, []).append(strike)
    return {exp: tuple(sorted(ks)) for exp, ks in out.items()}


@lru_cache(maxsize=None)
def _contract_marks(ticker: str, expiry: date, strike: float) -> dict[date, float]:
    """`{date: mark}` for one cached PUT — `_mark` only, missing rows absent."""
    path = cache_path(HISTORY_CACHE, ticker, expiry, strike, "Put")
    if not path.exists():
        return {}
    try:
        details = parse_history_details(path.read_text(), require_mark=True)
    except Exception:
        return {}
    return {d: r["_mark"] for d, r in details.items() if r.get("_mark") is not None}


@lru_cache(maxsize=None)
def _contract_series(ticker: str, expiry: date, strike: float
                     ) -> tuple[tuple[date, float], ...]:
    """The same marks as a sorted `((date, mark), ...)` — carry-forward input."""
    return tuple(sorted(_contract_marks(ticker, expiry, strike).items()))


def clear_caches() -> None:
    """Drop the per-contract caches.

    Only needed when the cache DIRECTORY itself changes under the module — a
    test pointing `HISTORY_CACHE` at a fixture tree. A study run never needs it:
    the cache on disk does not change mid-run, and the report header records
    which cache state produced it.
    """
    _put_index.cache_clear()
    _contract_marks.cache_clear()
    _contract_series.cache_clear()


def spot_on(ticker: str, day: date) -> float | None:
    """That session's close for the instrument, via `underlying.load_bars`.

    None when the session has no bar (a holiday mismatch, or a ticker with no
    cached history). Both fill rules are anchored on the close, so no spot
    means no pick — the session is unfillable, exactly as the plan-time
    coverage measurement counted it.
    """
    bar = U.load_bars(ticker).get(day)
    return bar.c if bar is not None else None


def instrument_excluded(ticker: str) -> bool:
    """True when the repo's own convention withholds this ticker as an instrument.

    Delegates to `underlying.rescaled_tickers()` rather than naming anyone: the
    exclusion is "its dollar moves are on a different basis", not "it is XLE".
    """
    return ticker.upper().strip() in U.rescaled_tickers()


# ── the picked put ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PutPick:
    """One long proxy put, selected on `session` under `rule` and fillable there."""
    ticker: str
    session: date
    expiry: date
    strike: float
    rule: str
    entry_mark: float
    spot: float

    @property
    def dte(self) -> int:
        return (self.expiry - self.session).days

    @property
    def moneyness(self) -> float:
        """|K − S| / S at entry. 0.0 is a real value here (a struck-at-spot put)."""
        return abs(self.strike - self.spot) / self.spot

    @property
    def leg(self) -> Leg:
        """The signed leg — a LONG put, one contract per unit."""
        return Leg(+1, self.ticker, self.expiry, self.strike, "Put")

    def label(self) -> str:
        cp = "P"
        return (f"{self.ticker} {self.expiry.isoformat()} {self.strike:g}{cp} "
                f"({self.rule}, {self.dte}d, {self.moneyness:+.1%})")


def _band_candidates(ticker: str, session: date, spot: float
                     ) -> list[tuple[date, float]]:
    """(expiry, strike) pairs inside the BAND rule, best first.

    Ranked by |DTE − 45|, then by |K − S|, then by (expiry, strike) so the pick
    is deterministic on a grown cache. The pre-registration fixes the band's
    WINDOWS but names no tie-break inside them; 45 DTE is the anchor it already
    commits to for the other rule and it sits inside 25–75, so both rules aim
    at the same point and differ only in how far they are allowed to stray.
    """
    lo_k, hi_k = spot * (1 - BAND_STRIKE_PCT), spot * (1 + BAND_STRIKE_PCT)
    out: list[tuple[date, float]] = []
    for expiry, strikes in _put_index(ticker).items():
        dte = (expiry - session).days
        if not BAND_DTE_LO <= dte <= BAND_DTE_HI:
            continue
        out.extend((expiry, k) for k in strikes if lo_k <= k <= hi_k)
    out.sort(key=lambda ek: (abs((ek[0] - session).days - NEAREST_ANCHOR_DTE),
                             abs(ek[1] - spot), ek[0], ek[1]))
    return out


def _nearest_candidates(ticker: str, session: date, spot: float
                        ) -> list[tuple[date, float]]:
    """(expiry, strike) pairs under NEAREST-AVAILABLE, best first.

    Expiries within 20–120 DTE ranked by |DTE − 45|; within an expiry, strikes
    at-or-below spot descending, so the first one QUOTED that day is the
    nearest quoted strike below spot — the same contract the plan-time coverage
    measurement resolved by filtering to quoted strikes and taking the max.
    """
    out: list[tuple[date, float]] = []
    expiries = [e for e in _put_index(ticker)
                if NEAREST_DTE_LO <= (e - session).days <= NEAREST_DTE_HI]
    expiries.sort(key=lambda e: (abs((e - session).days - NEAREST_ANCHOR_DTE), e))
    for expiry in expiries:
        below = [k for k in _put_index(ticker)[expiry] if k <= spot]
        out.extend((expiry, k) for k in reversed(below))
    return out


def select_put_verbose(ticker: str, session: date, rule: str = RULE_BAND
                       ) -> tuple[PutPick | None, str]:
    """`(pick | None, reason)` — the pick plus WHY there is not one.

    `reason` is `FILLED` on success, else one of `RESCALED` / `NO_SPOT` /
    `NO_CONTRACT` / `NO_MARK` / `BAD_RULE`. A caller that only wants the pick
    should use `select_put`; the reason exists so the study can report the
    shape of its unfillable sessions instead of a bare count.
    """
    if rule not in RULES:
        return None, BAD_RULE
    ticker = ticker.upper().strip()
    if instrument_excluded(ticker):
        return None, RESCALED
    spot = spot_on(ticker, session)
    if spot is None or spot <= 0:
        return None, NO_SPOT
    cands = (_band_candidates(ticker, session, spot) if rule == RULE_BAND
             else _nearest_candidates(ticker, session, spot))
    if not cands:
        return None, NO_CONTRACT
    for expiry, strike in cands:
        mark = _contract_marks(ticker, expiry, strike).get(session)
        if mark is None:
            continue
        return PutPick(ticker=ticker, session=session, expiry=expiry,
                       strike=strike, rule=rule, entry_mark=mark,
                       spot=spot), FILLED
    return None, NO_MARK


def select_put(ticker: str, session: date, rule: str = RULE_BAND) -> PutPick | None:
    """The long proxy put for `(ticker, session)` under `rule`, or None.

    None is the honest answer for an unfillable session — the study carries it
    at f=0 and counts it against G-FILL. Never substitute a modelled price.
    """
    return select_put_verbose(ticker, session, rule)[0]


# ── forward pricing of a picked put ──────────────────────────────────────────

def mark_on(pick: PutPick, day: date) -> float | None:
    """The put's mark on `day`, carry-forward priced and expiry-bounded.

    Mirrors `scripts/backtest/helpers.py::_price_asof`: the most recent mark on
    or before `day`, and never a mark stamped after the contract expired. None
    before the entry session and when nothing has printed yet.
    """
    if day < pick.session:
        return None
    best = None
    for snap, price in _contract_series(pick.ticker, pick.expiry, pick.strike):
        if snap > day or snap > pick.expiry:
            break
        best = price
    return best


def price_path(pick: PutPick, sessions) -> dict[date, float | None]:
    """`{session: mark|None}` over `sessions` — the mark-to-market carry.

    The caller decides what an unpriced day means for its curve; this returns
    None rather than the entry price, because "no quote" and "worth what we
    paid" are different claims.
    """
    return {d: mark_on(pick, d) for d in sessions}


def pnl_path(pick: PutPick, sessions, contracts: int) -> dict[date, float | None]:
    """`{session: dollars}` of open P&L on a LONG `contracts`-lot of the put.

    Entry mark is `pick.entry_mark`; a day with no carry-forward mark yields
    None, never 0.0 — an unpriced hedge is not a flat hedge.
    """
    out: dict[date, float | None] = {}
    for d in sessions:
        m = mark_on(pick, d)
        out[d] = (None if m is None
                  else (m - pick.entry_mark) * SHARES_PER_CONTRACT * contracts)
    return out


def entry_cost(pick: PutPick, contracts: int) -> float:
    """Debit paid for `contracts` of the pick, in dollars."""
    return pick.entry_mark * SHARES_PER_CONTRACT * contracts


def entry_delta(pick: PutPick, contracts: int = 1) -> float | None:
    """Signed delta of the position at entry, in SHARE-equivalents.

    Read from the cache through `lib/greeks.py`, which already refuses
    Barchart's all-zero sentinel greek block. **None when the greek is absent
    — never 0.0.** A long put's delta is negative, so this is the exposure the
    hedge removes.
    """
    d = G.leg_greek(pick.leg, pick.session, "Delta")
    if d is None:
        return None
    return d * SHARES_PER_CONTRACT * contracts


def harness_trade(pick: PutPick, contracts: int) -> Trade | None:
    """The picked put packed into the FROZEN `harness.Trade`, or None.

    Offered for a caller that wants exit replay on the hedge under the same
    engine every recorded conclusion rests on. The grid is rebuilt exactly as
    `Trade` rebuilds it (weekdays after the session, out to
    `min(DTE, PATH_CAP_DAYS)`), and marks are the carry-forward series, so
    `replay()` sees the shape it sees for a book row.

    The mark-to-market arms do NOT need this — `price_path` is the carry — and
    `harness.py` is never edited to accommodate it.
    """
    dte = pick.dte
    if dte <= 0 or contracts < 1:
        return None
    end = pick.session + timedelta(days=min(dte, PATH_CAP_DAYS))
    grid = _weekday_grid(pick.session, end)
    if not grid:
        return None
    marks = [mark_on(pick, d) for d in grid]
    if not any(m is not None for m in marks):
        return None
    leg = pick.leg
    row = {
        "signal_date": pick.session.isoformat(),
        "ticker": pick.ticker,
        "structure": "long_put",
        "entry_option_price": f"{pick.entry_mark:.4f}",
        "contracts": str(int(contracts)),
        "dte_entry": str(dte),
        "legs": (f"{leg.ticker}:{leg.expiration.isoformat()}:{leg.strike:g}:P "
                 f"{leg.qty:+d}"),
        "daily_price_csv": ",".join("" if m is None else f"{m:.4f}" for m in marks),
    }
    try:
        return Trade(row)
    except (AssertionError, ValueError, KeyError):
        return None


# ── ARM R: the delta-equivalent underlying short ─────────────────────────────

@dataclass(frozen=True)
class UnderlyingShort:
    """A position in the proxy UNDERLYING, sized in SIGNED shares.

    Negative shares are a short, which is what every ARM R position is: the arm
    carries the SAME delta as the put it stands in for, and a long put's delta
    is negative. The sign is carried explicitly rather than implied by the
    class name, because a silently flipped hedge would show up as a
    plausible-looking curve that moves the wrong way.

    Shares are NOT rounded to a lot. The pre-registration's known sizing defect
    — `max(1, int(f × contracts))` silently becoming full size at one contract
    — is an OPTION-CONTRACT defect; there is no minimum lot here, so ARM R
    carries the requested fraction exactly and the study states that rather
    than inheriting a floor it does not have.

    ARM R is a FLOOR ON FEASIBILITY, not a recommendation: it has a different
    loss shape from a put and is not an instrument the operator trades.
    """
    ticker: str
    session: date
    entry_price: float
    shares: float

    @property
    def delta_notional(self) -> float:
        """Signed dollar delta at entry — negative for the short it is."""
        return self.shares * self.entry_price


def underlying_position(ticker: str, session: date, shares: float
                        ) -> UnderlyingShort | None:
    """`shares` of `ticker` filled at that session's close. SIGNED: negative = short.

    Always fillable by construction — the only None cases are an excluded
    instrument and a session with no bar, which is why ARM R cannot terminate
    the study on fill coverage the way `calendar_hedge` ended.
    """
    ticker = ticker.upper().strip()
    if instrument_excluded(ticker):
        return None
    spot = spot_on(ticker, session)
    if spot is None or spot <= 0:
        return None
    return UnderlyingShort(ticker=ticker, session=session, entry_price=spot,
                           shares=float(shares))


def short_for_delta_notional(ticker: str, session: date, delta_notional: float
                             ) -> UnderlyingShort | None:
    """ARM R sized off a SIGNED dollar delta the hedge is to CARRY.

    Pass a NEGATIVE notional to stand against a long book: the sign convention
    is the position's own, not "how much exposure to cancel", so nothing here
    silently inverts a caller's number.
    """
    spot = spot_on(ticker, session)
    if spot is None or spot <= 0:
        return None
    return underlying_position(ticker, session, delta_notional / spot)


def delta_equivalent_short(pick: PutPick, contracts: int
                           ) -> UnderlyingShort | None:
    """ARM R matched to an ARM C put: the SAME entry delta, none of the convexity.

    The put's entry delta is negative, so the returned position is short — that
    is the whole point of the arm, which exists to carry the pure
    exposure-reduction effect so clause 7 of the bar can ask whether a put arm
    is anything more than a delta reduction in disguise.

    None when the put's entry delta is unavailable — a missing greek is None,
    never 0.0, and a fabricated 0.0 would size the reference arm at zero and
    make the put look better than it is by exactly the missing exposure.
    """
    d = entry_delta(pick, contracts)
    if d is None:
        return None
    return underlying_position(pick.ticker, pick.session, d)


def short_mark_on(pos: UnderlyingShort, day: date) -> float | None:
    """The underlying's close on `day`, or None when there is no bar."""
    if day < pos.session:
        return None
    return spot_on(pos.ticker, day)


def short_pnl_path(pos: UnderlyingShort, sessions) -> dict[date, float | None]:
    """`{session: dollars}` of open P&L on the short. None on a bar-less day."""
    out: dict[date, float | None] = {}
    for d in sessions:
        p = short_mark_on(pos, d)
        out[d] = None if p is None else pos.shares * (p - pos.entry_price)
    return out


# ── G-FILL: fill coverage ────────────────────────────────────────────────────

@dataclass(frozen=True)
class FillCoverage:
    """Fill coverage of one rule over a set of (session, proxy) pairs.

    `n` is every pair asked about, INCLUDING the ones whose proxy is excluded
    or unquoted: per the pre-registration an unfillable session is carried at
    f=0 and counted against the gate, never dropped from the denominator.
    """
    rule: str
    n: int
    filled: int
    by_proxy: dict[str, tuple[int, int]]     # ticker -> (filled, n)
    by_reason: dict[str, int]                # reason -> count (FILLED included)

    @property
    def rate(self) -> float:
        return self.filled / self.n if self.n else 0.0

    def proxy_rate(self, ticker: str) -> float:
        f, n = self.by_proxy.get(ticker.upper().strip(), (0, 0))
        return f / n if n else 0.0

    def passes(self, gate: float = FILL_GATE) -> bool:
        """G-FILL. Below the gate the proxy-put arms are NOT EVALUABLE — which
        is not the same as failed, and only ARM R is read."""
        return self.n > 0 and self.rate >= gate


def fill_coverage(pairs, rule: str = RULE_BAND) -> FillCoverage:
    """Coverage of `rule` over an iterable of `(session, proxy_ticker)` pairs.

    Every pair is evaluated; duplicates are counted as given, because the gate
    is read on TRIGGERED SESSIONS and a proxy triggered twice is two sessions.
    """
    filled = 0
    n = 0
    by_proxy: dict[str, list[int]] = {}
    by_reason: dict[str, int] = {}
    for session, ticker in pairs:
        tk = str(ticker).upper().strip()
        _, reason = select_put_verbose(tk, session, rule)
        ok = reason == FILLED
        n += 1
        filled += int(ok)
        cell = by_proxy.setdefault(tk, [0, 0])
        cell[0] += int(ok)
        cell[1] += 1
        by_reason[reason] = by_reason.get(reason, 0) + 1
    return FillCoverage(rule=rule, n=n, filled=filled,
                        by_proxy={k: (v[0], v[1]) for k, v in sorted(by_proxy.items())},
                        by_reason=dict(sorted(by_reason.items())))


def coverage_table(pairs, rules=RULES) -> dict[str, FillCoverage]:
    """`{rule: FillCoverage}` for both committed rules over the same pairs."""
    pairs = list(pairs)
    return {rule: fill_coverage(pairs, rule) for rule in rules}
