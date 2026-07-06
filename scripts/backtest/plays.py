"""Polymorphic play model — Pass 1 (classify → build legs) and Pass 3 (simulate).

Each trade *structure* is a :class:`Play` subclass grouped by shared behavior. A
registry maps every classifier structure name to its class, so both passes dispatch
by lookup instead of an ``if/elif`` chain:

  • Pass 1 — :func:`build_matched_plays` classifies each candidate, calls the matching
    class's :meth:`Play.build` to construct legs (or, for iron condors, defer the wings),
    and records the contracts whose Barchart history must be fetched.
  • Pass 3 — :meth:`Play.simulate` resolves the entry row and runs :func:`_simulate`.
    The base class implements the common path (a fixed anchor leg); only
    :class:`ExplicitPlay` (dynamic anchor) and :class:`IronCondorPlay` (wings resolved
    from the entry underlying) override it.

This replaces the old loose ``matched`` dict and its two parallel ``if/elif`` blocks.
"""
import logging
from abc import ABC, abstractmethod

from .classify import (classify_play, _extract_all_expirations,
                       _entry_row_from_history, _resolve_expiry)
from .config import HISTORY_CACHE
from .helpers import _contract_key, _to_float, _short_strike
from .legs import (legs_from_structure, iron_condor_legs, merge_legs,
                   straddle_legs, strangle_legs, butterfly_legs, condor_legs,
                   calendar_legs, diagonal_legs)
from .simulate import _simulate, _iron_condor_strikes

log = logging.getLogger("backtest")


# ─── Pass-1 / Pass-3 leg helpers ────────────────────────────────────────────────

def _register(contracts: dict, needed_dates: dict, ticker: str, opt_type: str,
              strike: float, exp_date, sig) -> None:
    """Record a distinct contract to fetch Barchart history for, tracking the
    earliest signal date that needs it."""
    key = _contract_key(ticker, opt_type, strike, exp_date.isoformat())
    contracts.setdefault(key, {"key": key, "symbol": ticker, "opt_type": opt_type,
                               "strike": strike, "expiration": exp_date})
    if key not in needed_dates or sig < needed_dates[key]:
        needed_dates[key] = sig


def _choose_anchor(legs, barchart_details, signal_date, timing="signal_eod"):
    """Pick the anchor leg for an explicit structure and build its entry row.

    The anchor seeds the position's entry IV / underlying / DTE from its Barchart
    history. Legs are tried in priority order — long legs first, then by descending
    |qty| — and the first whose history yields a valid entry row wins, so a play is
    no longer dropped just because one (e.g. illiquid) wing has no data. Returns
    (anchor_idx, entry_row) or (None, None) when no leg has usable history.
    """
    order = sorted(range(len(legs)), key=lambda i: (legs[i].qty <= 0, -abs(legs[i].qty)))
    for i in order:
        leg = legs[i]
        key = _contract_key(leg.ticker, leg.opt_type, leg.strike, leg.expiration.isoformat())
        row = _entry_row_from_history(barchart_details, key, signal_date, leg.strike,
                                      leg.expiration, timing=timing)
        if row is not None:
            return i, row
    return None, None


# ─── Play hierarchy ─────────────────────────────────────────────────────────────

class Play(ABC):
    """A classified play. Subclass per structure family.

    Pass 1 = :meth:`build` (classmethod factory); Pass 3 = :meth:`simulate`.
    Replaces the old ``matched`` dict — instances carry everything the two passes
    need: the candidate row (``c``), the classifier output (``cls``), the built
    ``legs`` (``None`` for iron condors until the entry underlying is known), the
    fixed ``anchor`` contract + ``anchor_idx``, and the ``contracts`` whose Barchart
    history must be fetched.
    """
    structures: tuple[str, ...] = ()  # classifier structure names this class handles

    def __init__(self, c, cls, *, structure, legs=None, anchor=None,
                 anchor_idx=0, contracts=None):
        self.c = c
        self.cls = cls
        self.structure = structure
        self.legs = legs
        self.anchor = anchor          # (ticker, opt_type, strike, exp) | None
        self.anchor_idx = anchor_idx
        self.contracts = contracts or []  # [(ticker, opt_type, strike, exp), ...]

    # ── Pass 1 ──────────────────────────────────────────────────────────────────
    @classmethod
    @abstractmethod
    def build(cls, c, play_cls, spread_pct):
        """Construct the play from a candidate + its classifier output.

        Returns ``(instance, None)`` on success or ``(None, (skip_category, message))``
        on failure (the caller logs uniformly and tallies ``skip_category``).
        """

    # ── Pass 3 ──────────────────────────────────────────────────────────────────
    def simulate(self, barchart_series, barchart_details, sim_cfg, spread_pct):
        """Default path: fixed anchor → entry row from Barchart history → simulate.

        Returns the result dict, or ``None`` (after logging the skip) when the anchor
        has no usable history or the position cannot be priced.
        """
        c = self.c
        a_ticker, a_type, a_K, a_exp = self.anchor
        anchor_key = _contract_key(a_ticker, a_type, a_K, a_exp.isoformat())
        entry_row = _entry_row_from_history(
            barchart_details, anchor_key, c["signal_date"], a_K, a_exp,
            timing=sim_cfg.get("entry_timing", "next_open"))
        if entry_row is None:
            log.warning("SKIP unpriced     %s %s | no history on/after signal date for %s",
                        c["signal_date"], c["ticker"], anchor_key)
            return None
        return self._simulate(c, self.legs, entry_row, barchart_series, sim_cfg,
                              self.anchor_idx, barchart_details)

    def _simulate(self, c, legs, entry_row, barchart_series, sim_cfg, anchor_idx,
                  barchart_details=None):
        """Run :func:`_simulate`, logging a uniform skip when it can't price."""
        result = _simulate(c, legs, entry_row, {}, barchart_series, sim_cfg,
                           structure=self.structure, anchor_idx=anchor_idx,
                           barchart_details=barchart_details)
        if not result:
            log.warning("SKIP simulate={}  %s %s | %s",
                        c["signal_date"], c["ticker"], self.structure)
            return None
        return result


class ExplicitPlay(Play):
    """Fully-specified legs (e.g. ``+3 AMD:2025-10-16:130:C``). Every leg is a real
    contract; the anchor is chosen at simulate time from whichever leg has history."""
    structures = ("explicit_legs",)

    @classmethod
    def build(cls, c, play_cls, spread_pct):
        legs = merge_legs(play_cls["legs"])
        if not legs:
            return None, ("unpriced", "explicit legs merged to empty")
        contracts = [(leg.ticker, leg.opt_type, leg.strike, leg.expiration) for leg in legs]
        return cls(c, play_cls, structure="explicit_legs", legs=legs,
                   contracts=contracts), None

    def simulate(self, barchart_series, barchart_details, sim_cfg, spread_pct):
        c = self.c
        anchor_idx, entry_row = _choose_anchor(
            self.legs, barchart_details, c["signal_date"],
            timing=sim_cfg.get("entry_timing", "next_open"))
        if entry_row is None:
            log.warning("SKIP unpriced     %s %s | no history on/after signal date for any leg",
                        c["signal_date"], c["ticker"])
            return None
        return self._simulate(c, self.legs, entry_row, barchart_series, sim_cfg, anchor_idx,
                              barchart_details)


class CalendarDiagonalPlay(Play):
    """Calendar / diagonal: two explicit expirations (near + far), same or split strike."""
    structures = ("calendar", "diagonal")

    @classmethod
    def build(cls, c, play_cls, spread_pct):
        structure = play_cls["structure"]
        exps = _extract_all_expirations(c["play"], c["signal_date"])
        if len(exps) < 2:
            return None, ("no_expiry", f"{structure} requires 2 explicit expirations")
        exp_near, exp_far = exps[0], exps[1]
        play_strikes = play_cls.get("strikes", [])
        if not play_strikes:
            return None, ("no_strike", f"{structure}: no strike in play text")
        opt_type = play_cls.get("option_type") or "Call"
        is_credit = play_cls.get("is_credit", False)
        ticker = c["ticker"]
        if structure == "calendar":
            K = play_strikes[0]
            legs = calendar_legs(ticker, exp_near, exp_far, K, opt_type, is_credit)
        else:  # diagonal
            if len(play_strikes) >= 2:
                K_lo, K_hi = sorted(play_strikes[:2])
                # Long diagonal: far leg takes the more-favorable strike.
                K_far  = K_lo if opt_type == "Call" else K_hi
                K_near = K_hi if opt_type == "Call" else K_lo
            else:
                K_far = K_near = play_strikes[0]
            legs = diagonal_legs(ticker, exp_near, exp_far, K_far, K_near, opt_type, is_credit)
        anchor = legs[0]  # far (long) leg
        contracts = [(leg.ticker, leg.opt_type, leg.strike, leg.expiration) for leg in legs]
        return cls(c, play_cls, structure=structure, legs=legs, anchor_idx=0,
                   anchor=(anchor.ticker, anchor.opt_type, anchor.strike, anchor.expiration),
                   contracts=contracts), None


class IronCondorPlay(Play):
    """Iron condor. The short put is the flow-matched anchor; the four strikes are
    resolved at simulate time from the entry underlying (wings may be synthesized)."""
    structures = ("iron_condor",)

    @classmethod
    def build(cls, c, play_cls, spread_pct):
        ic_strikes = play_cls.get("strikes", [])
        if not ic_strikes:
            return None, ("no_strike", "iron condor: no strikes in play text")
        # Anchor = the short put (index 1 of the 4 sorted strikes, else the lone strike).
        # An IC is both-sided; "Put" here names the anchor leg only, not a direction.
        K = ic_strikes[1] if len(ic_strikes) >= 4 else ic_strikes[0]
        exp, skip = _resolve_expiry(c, "Put", K, HISTORY_CACHE)
        if exp is None:
            return None, skip
        # Always fetch the short-put anchor. When all 4 strikes are explicit, also
        # fetch the wings; synthesized wings (from spread_pct) may not be listed and
        # fall back to BS at price time.
        contracts = [(c["ticker"], "Put", K, exp)]
        if len(ic_strikes) >= 4:
            K_lp, K_sp, K_sc, K_lc = sorted(ic_strikes)[:4]
            contracts += [(c["ticker"], "Put", K_lp, exp),
                          (c["ticker"], "Call", K_sc, exp),
                          (c["ticker"], "Call", K_lc, exp)]
        return cls(c, play_cls, structure="iron_condor", legs=None, anchor_idx=1,
                   anchor=(c["ticker"], "Put", K, exp), contracts=contracts), None

    def simulate(self, barchart_series, barchart_details, sim_cfg, spread_pct):
        c = self.c
        a_ticker, a_type, a_K, a_exp = self.anchor
        anchor_key = _contract_key(a_ticker, a_type, a_K, a_exp.isoformat())
        entry_row = _entry_row_from_history(
            barchart_details, anchor_key, c["signal_date"], a_K, a_exp,
            timing=sim_cfg.get("entry_timing", "next_open"))
        if entry_row is None:
            log.warning("SKIP unpriced     %s %s | no history on/after signal date for %s",
                        c["signal_date"], c["ticker"], anchor_key)
            return None
        # Resolve the four IC strikes now that the entry underlying is known.
        S_entry = _to_float(entry_row.get("Price~", entry_row.get("Price")))
        if not S_entry:
            log.warning("SKIP unpriced     %s %s | no entry underlying for iron condor",
                        c["signal_date"], c["ticker"])
            return None
        K_lp, K_sp, K_sc, K_lc = _iron_condor_strikes(
            self.cls.get("strikes", []), a_K, S_entry, spread_pct)
        legs = iron_condor_legs(c["ticker"], a_exp, K_lp, K_sp, K_sc, K_lc)
        return self._simulate(c, legs, entry_row, barchart_series, sim_cfg, self.anchor_idx,
                              barchart_details)


class MultiLegPlay(Play):
    """Same-expiration multi-leg structures: straddle / strangle / butterfly / condor.

    These resolve their own anchor (no K_short, unlike a vertical), so they share only
    ``_resolve_expiry``; resolving a contra strike is left to ``SingleOrVerticalPlay``.
    Note the two flavours of ``opt_type``:
      • straddle / strangle are *both-sided* (call + put) — ``opt_type`` names the ANCHOR
        leg (index 0); the other leg is the opposite type.
      • butterfly / condor are *same-type* — ``opt_type`` is the uniform leg type.
    """
    structures = ("straddle", "strangle", "butterfly", "condor")

    @classmethod
    def build(cls, c, play_cls, spread_pct):
        opt_type = play_cls.get("option_type")
        if not opt_type:
            return None, ("no_strike", "no option_type resolved")
        play_strikes = play_cls.get("strikes", [])
        if not play_strikes:
            return None, ("no_strike", "no strikes in play text")
        K = play_strikes[0]  # fallback anchor strike when explicit strikes are missing
        exp_date, skip = _resolve_expiry(c, opt_type, K, HISTORY_CACHE)
        if exp_date is None:
            return None, skip

        structure = play_cls["structure"]
        is_credit = play_cls.get("is_credit", False)
        ticker = c["ticker"]

        if structure == "straddle":
            legs = straddle_legs(ticker, exp_date, K, opt_type, is_credit)
        elif structure == "strangle":
            if len(play_strikes) >= 2:
                K_lo, K_hi = sorted(play_strikes[:2])
                K_anchor = K_lo if opt_type == "Put" else K_hi
                K_other  = K_hi if opt_type == "Put" else K_lo
            else:
                K_anchor = K
                K_other  = K * (1 + spread_pct) if opt_type == "Put" else K * (1 - spread_pct)
            legs = strangle_legs(ticker, exp_date, K_anchor, K_other, opt_type, is_credit)
        elif structure == "butterfly":
            if len(play_strikes) >= 3:
                K_lo, K_mid, K_hi = sorted(play_strikes[:3])
            else:
                K_lo = K
                K_mid = K * (1 + spread_pct)
                K_hi  = K * (1 + 2 * spread_pct)
            legs = butterfly_legs(ticker, exp_date, K_lo, K_mid, K_hi, opt_type, is_credit)
        else:  # condor
            if len(play_strikes) >= 4:
                K1, K2, K3, K4 = sorted(play_strikes[:4])
            else:
                K1 = K
                K2 = K * (1 + spread_pct)
                K3 = K * (1 + 2 * spread_pct)
                K4 = K * (1 + 3 * spread_pct)
            legs = condor_legs(ticker, exp_date, K1, K2, K3, K4, opt_type, is_credit)

        anchor = legs[0]
        contracts = [(leg.ticker, leg.opt_type, leg.strike, leg.expiration) for leg in legs]
        return cls(c, play_cls, structure=structure, legs=legs, anchor_idx=0,
                   anchor=(anchor.ticker, anchor.opt_type, anchor.strike, anchor.expiration),
                   contracts=contracts), None


class SingleOrVerticalPlay(Play):
    """Single-leg options and two-leg verticals — mapped onto signed legs by
    :func:`legs_from_structure`."""
    structures = ("long_call", "long_put", "short_call", "short_put",
                  "bull_call_spread", "bear_put_spread",
                  "bear_call_spread", "bull_put_spread")

    @classmethod
    def build(cls, c, play_cls, spread_pct):
        # The only structure with a true direction AND a contra leg, so it's the only
        # one that resolves a short strike (K_short) — single-leg structures get None.
        opt_type = play_cls.get("option_type")
        if not opt_type:
            return None, ("no_strike", "no option_type resolved")
        strikes = play_cls.get("strikes", [])
        if not strikes:
            return None, ("no_strike", "no strikes in play text")
        structure = play_cls["structure"]
        K = strikes[0]
        exp_date, skip = _resolve_expiry(c, opt_type, K, HISTORY_CACHE)
        if exp_date is None:
            return None, skip
        K_short = _short_strike(structure, K, strikes, spread_pct)
        is_credit = play_cls.get("is_credit", False)
        legs = merge_legs(legs_from_structure(
            structure, opt_type, c["ticker"], exp_date, K, K_short, is_credit))
        anchor = legs[0]
        contracts = [(leg.ticker, leg.opt_type, leg.strike, leg.expiration) for leg in legs]
        return cls(c, play_cls, structure=structure, legs=legs, anchor_idx=0,
                   anchor=(anchor.ticker, anchor.opt_type, anchor.strike, anchor.expiration),
                   contracts=contracts), None


_REGISTRY = {s: C for C in (ExplicitPlay, CalendarDiagonalPlay, IronCondorPlay,
                            MultiLegPlay, SingleOrVerticalPlay) for s in C.structures}


# ─── TF-S structure override (config-gated experiment) ───────────────────────────

# Bullish / bearish DEBIT verticals → their SAME-DIRECTION credit counterpart.
# {debit_structure: (credit_structure, credit_leg_option_type)}. The framework's
# TF-S rule (config/analysis-framework.md Step 4): a trend name in a rich-IV,
# positive-gamma slow grind should be expressed with a CREDIT spread, because a
# debit buys premium the slow move can't overcome. This transform lets the backtest
# A/B that rule on EXISTING debit plays without re-running the LLM.
#
# APPROXIMATE: the play's cited strikes are reused, so the resulting credit spread
# sits at the original strike zone rather than a freshly-chosen OTM band. It is a
# mechanical hypothesis test, not a faithful re-selection — the faithful path is the
# framework/prompt change that makes the model emit TF-S credit plays directly
# (validate that on a fresh run). Default OFF (see config/backtest.yml).
_TF_S_DEBIT_TO_CREDIT = {
    "bull_call_spread": ("bull_put_spread", "Put"),
    "bear_put_spread":  ("bear_call_spread", "Call"),
}


def _is_positive_gamma_grind(c) -> bool:
    """Proxy for the positive-gamma / contango slow-grind regime (framework Step 4,
    until per-name GEX ships): the market/ticker regime reads BULL and is NOT flagged
    as an expanding-vol environment (E-VOL / H-VOL)."""
    reg = f"{c.get('market_regime', '')} {c.get('regime', '')}".upper()
    if "BULL" not in reg:
        return False
    return not any(v in reg for v in ("E-VOL", "H-VOL"))


def apply_tf_s_override(cls: dict, c: dict, cfg: dict | None) -> dict:
    """Rewrite a TF debit vertical → its credit counterpart when IV is rich and the
    regime is a positive-gamma grind (the TF-S case). Config-gated; a no-op unless
    ``cfg['enabled']`` is set. Returns the (possibly rewritten) classifier dict.

    Gates: structure is one of :data:`_TF_S_DEBIT_TO_CREDIT`, the play's ``iv_pct``
    (a decimal fraction) is ``>= cfg['iv_pct_threshold']`` (default 0.70), and the
    regime clears :func:`_is_positive_gamma_grind`. A blank/absent ``iv_pct`` never
    overrides — the play is left as the analysis wrote it.
    """
    if not cfg or not cfg.get("enabled"):
        return cls
    mapping = _TF_S_DEBIT_TO_CREDIT.get(cls.get("structure"))
    if mapping is None:
        return cls
    try:
        iv_pct = float(c.get("iv_pct"))  # stored as a decimal fraction (0.70 = 70th pct)
    except (TypeError, ValueError):
        return cls  # blank IVpct → no override
    if iv_pct < cfg.get("iv_pct_threshold", 0.70) or not _is_positive_gamma_grind(c):
        return cls
    structure, opt_type = mapping
    log.info("TF-S override     %s %s | %s → %s (IVpct %.0f%%)",
             c.get("date"), c.get("ticker"), cls.get("structure"), structure, iv_pct * 100)
    out = dict(cls)
    out["structure"] = structure
    out["option_type"] = opt_type
    out["is_credit"] = True
    return out


# ─── Pass 1 driver ──────────────────────────────────────────────────────────────

def classify_and_build(c, spread_pct, tf_s_override=None):
    """Classify + build ONE candidate. Returns (play|None, reason|None),
    reason = (category, message) with the existing categories
    unsupported/no_strike/no_expiry/unpriced.

    Factored out of :func:`build_matched_plays` so a single candidate can be
    classified+built in isolation (re-exported from ``scripts/backtest/shared``
    for reuse outside this Pass-1 driver's tally/logging loop).
    """
    c["regime"] = c.get("regime", "")
    cls = classify_play(c["play"])
    cls = apply_tf_s_override(cls, c, tf_s_override)
    structure = cls["structure"]
    play_type = _REGISTRY.get(structure)
    if play_type is None:
        return None, ("unsupported", f"structure={structure}")
    return play_type.build(c, cls, spread_pct)


def build_matched_plays(candidates, spread_pct, tf_s_override=None):
    """Pass 1 — classify each candidate into a :class:`Play` and register its contracts.

    Returns ``(plays, contracts, needed_dates, skipped)``:
      • ``plays``        — list of built :class:`Play` instances (ready for Pass 3)
      • ``contracts``    — {contract_key: {key,symbol,opt_type,strike,expiration}} to fetch
      • ``needed_dates`` — {contract_key: earliest signal date needing it}
      • ``skipped``      — per-category skip tally
    """
    plays, contracts, needed_dates = [], {}, {}
    skipped = {"unsupported": 0, "no_strike": 0, "no_expiry": 0, "unpriced": 0}
    for c in candidates:
        play, skip = classify_and_build(c, spread_pct, tf_s_override)
        if skip:
            category, message = skip
            skipped[category] += 1
            log.warning("SKIP %-12s %s %s | %s | play=%s",
                        category, c["date"], c["ticker"], message, c["play"][:80])
            continue
        sig = c["signal_date"]
        for (ticker, opt_type, strike, exp) in play.contracts:
            _register(contracts, needed_dates, ticker, opt_type, strike, exp, sig)
        plays.append(play)
    return plays, contracts, needed_dates, skipped
