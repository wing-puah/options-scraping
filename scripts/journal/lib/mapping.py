"""
The journal's rules vocabulary: structure names, match confidences, the ladder.

PRODUCTION TIER, pure computation. This is where the daily journal keeps the
rules that name what was traded and score it against the analysis that proposed
it: turning a group of filled option legs into a canonical structure family,
matching that against an AnalysisClaude play on its signal date, and
reconstructing the deployment-ladder tier the play would have received.

`ladder_tier()` is the ONLY encoding of `docs/deployment-rules.md` §1-§3 —
there must never be a second copy. Anything that needs to know a structure's
tier (the daily journal, the deploy card, the research tier's live_select
layer) calls this function; do not re-derive the veto/tier rules inline
elsewhere.

IT SPEAKS THE JOURNAL'S OWN TYPES. Every leg-shaped argument here is a
`config.Leg` — the same object `lib/rawpull.py` builds from a fill and from an
open position — and every position-shaped argument is a list of them. Until
2026-09-09 this module was shared with `scripts/live_loop/stage1_map_fills.py`,
a fortnightly audit that reconstructed positions from a hand-pasted MCP
snapshot with no broker contract id, so it took a bespoke
`{"trade": ..., "match": ...}` dict shape and three callers carried adapters to
dress `Leg`s up as it. That script was RETIRED on 2026-09-09 — the daily
journal reads Flex, which carries strike and expiry on every fill, and
supersedes it — so the dict shape and its adapters are gone. Its snapshots stay
under `backtests/live_loop/` as protected data.

ONE CONSEQUENCE OF THAT, WORTH STATING. A `Leg` always knows its strike,
expiry, right and signed quantity, so the "identity could not be pinned"
branches the snapshot format needed (a round-trip close named
`single long option (debit), strike/expiry UNKNOWN`) are unreachable and are
not carried here. `_live_to_canonical()` still maps that legacy label to
`"unknown"`, because rows written under it are still in `journal/trades.csv`.

What is deliberately NOT here: broker transport, pull loading, fill grouping
and report emission. This module only knows about *leg groups* and *analysis
rows* — it has no opinion on where either came from.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from lib.structure_names import canonical_spread_names

if TYPE_CHECKING:  # `..config` imports CONFIDENCES from here — a runtime import
    from ..config import Leg  # would be circular, and annotations are strings.


# --------------------------------------------------------------------------
# Orientation: a structure label names a POSITION, not an ORDER
# --------------------------------------------------------------------------
def position_legs(legs: list[Leg], *, closing: bool) -> list[Leg]:
    """`legs` oriented to the position they act on. `closing=True` flips signs.

    THIS IS THE P1 FIX (robustness-review P1, 2026-09-07). A `Leg`'s `qty` is
    the signed quantity of the FILL, which equals the signed POSITION only when
    the fill OPENED it. A closing fill is the position's mirror image: selling
    the 170 and buying back the 180 of a bull call spread reads, sign for sign,
    as a bear call spread, and `ladder_tier()` vetoes that on sight. Every
    closed spread journalled before 2026-09-07 carries the inverted label.

    So the caller decides the ACTION first and orients the group to the position
    it acts on. Everything downstream then describes that position: the
    structure label, `decompose_core()`'s financed-vertical split, the overlay
    test, the analysis match and the tier.

    ONLY A WHOLE-GROUP CLOSE IS ORIENTED. A ROLL closes one leg while opening
    another and a PARTIAL does not know which it did, so neither names a single
    position; both keep the fill-sign reading and the caller discloses it.

    ORIENTATION MUST NOT TOUCH MONEY. `net_price()` is deliberately a separate
    function and is always called on the UNORIENTED legs: a label names the
    position, but cash names the transaction, and inverting the journal's
    `net_price` would misreport what was actually paid or received.
    """
    if not closing:
        return list(legs)
    return [replace(lg, qty=-lg.qty) for lg in legs]


def net_price(legs: list[Leg]) -> float:
    """Net price per share of a leg group: positive debit, negative credit.

    Read from the legs' own signs, so calling this on the unoriented fills
    gives the transaction's cash and calling it on `position_legs(...,
    closing=True)` gives the closed position's side. Commission is not folded
    in — the journal records it as its own column, all-or-nothing across legs.
    """
    return sum(_leg_sign(lg) * float(lg.fill_price) for lg in legs)


def _leg_sign(lg: Leg) -> int:
    """+1 long, -1 short. A zero quantity reads short, as the fill side did."""
    return 1 if lg.qty > 0 else -1


# --------------------------------------------------------------------------
# Structure classification (a leg group -> a canonical structure label)
# --------------------------------------------------------------------------
def classify_structure(legs: list[Leg], open_book: list[Leg] = ()
                       ) -> tuple[str, str, bool]:
    """Return `(structure_label, note, is_overlay)` for one leg group.

    `legs` must already be oriented — see `position_legs()`. `open_book` is the
    broker's currently-held option legs (`rawpull.open_legs()`), used only by
    the overlay test; pass nothing when the book of the day is not recoverable.
    """
    net = net_price(legs)
    debit_credit = "debit" if net > 0 else "credit"

    # -- single leg --
    if len(legs) == 1:
        lg = legs[0]
        side = "long" if lg.qty > 0 else "short"
        right = "call" if lg.right == "C" else "put"
        label = f"single {side} {right}"
        # overlay = short single-expiry leg over a same-ticker position at
        # another expiry
        is_overlay = _is_overlay(lg, open_book)
        if is_overlay:
            label += " (overlay)"
        return label, "", is_overlay

    # -- two-leg combos --
    if len(legs) == 2:
        a, b = legs
        if a.expiry != b.expiry:
            return ("diagonal/calendar (mixed expiry)",
                    "legs span two expiries — not a vertical", True)
        return _vertical_label(a, b, debit_credit), "", False

    return f"{len(legs)}-leg combo ({debit_credit})", "", False


def _vertical_label(a: Leg, b: Leg, debit_credit: str) -> str:
    """Canonical name for a same-expiry two-leg pair, from its rights and signs.

    Extracted from `classify_structure`'s two-leg branch so the core of a
    multi-leg structure (see `decompose_core`) is named by the SAME rules a
    standalone vertical is. Two encodings of "what is a bull call spread" would
    let a financed spread and a plain one disagree about their own name.
    """
    rights = {a.right, b.right}
    # sort by strike
    lo, hi = (a, b) if a.strike < b.strike else (b, a)
    lo_pos = lo.qty  # <0 short, >0 long
    hi_pos = hi.qty
    if rights == {"C"}:
        if lo_pos > 0 and hi_pos < 0:
            return "bull_call_spread"
        if lo_pos < 0 and hi_pos > 0:
            return "bear_call_spread"
        return f"call vertical ({debit_credit})"
    if rights == {"P"}:
        if hi_pos < 0 and lo_pos > 0:
            return "bull_put_spread"
        if hi_pos > 0 and lo_pos < 0:
            return "bear_put_spread"
        return f"put vertical ({debit_credit})"
    return f"mixed C/P vertical ({debit_credit})"


def _is_overlay(leg: Leg, open_book: list[Leg]) -> bool:
    """A single SHORT leg is an overlay when the same ticker already holds open
    option legs at a different expiry — i.e. it sits on top of a spread."""
    if leg.qty >= 0:
        return False
    return any(p.symbol == leg.symbol and p.expiry != leg.expiry
               for p in open_book)


def decompose_core(legs: list[Leg]):
    """Split a multi-leg group into `(core_pair, overlay_legs)`, or `(None, [])`.

    THE STRATEGY THIS MODELS. The operator trades a core debit vertical and
    sells a further leg — usually shorter-dated, always short — to finance it.
    The broker reports one N-leg combo, and `classify_structure` can only call it
    `"3-leg combo (debit)"`. That label canonicalises to `"unknown"`, which has
    no SIDE/DIRECTION entry, so `map_entry` rejects it outright and the trade
    scores NONE against an analysis play it was in fact built from. Naming the
    CORE is what lets the match be made against the play that was emitted.

    UNDECIDABLE MEANS UNDECIDABLE. Every ambiguity below returns `(None, [])`
    and the caller falls back to today's behaviour. Guessing a core would put a
    fabricated structure in front of `ladder_tier`, which is the one thing worse
    than reporting no match at all.
    """
    legs = list(legs or [])
    if len(legs) < 3:
        return None, []
    for lg in legs:
        # A Leg built from a fill or a position always carries these; one
        # rebuilt from a partial record may not, and a missing field makes the
        # group undecidable rather than raising.
        if any(getattr(lg, k, None) is None
               for k in ("expiry", "right", "strike", "qty")):
            return None, []

    # Candidate cores: a same-expiry, same-right pair at different strikes with
    # opposite signs — the shape of every vertical.
    candidates = []
    for i in range(len(legs)):
        for j in range(i + 1, len(legs)):
            a, b = legs[i], legs[j]
            if a.expiry != b.expiry or a.right != b.right:
                continue
            if a.strike == b.strike:
                continue
            if _leg_sign(a) * _leg_sign(b) >= 0:
                continue
            candidates.append((a, b, [lg for k, lg in enumerate(legs)
                                      if k not in (i, j)]))
    if not candidates:
        return None, []

    # 1. Every leftover leg must be SHORT. A financing overlay is short by
    #    definition — that is what makes it financing. A long leftover means
    #    this is some other structure and we do not know its shape.
    candidates = [c for c in candidates
                  if all(_leg_sign(lg) < 0 for lg in c[2])]
    if not candidates:
        return None, []

    # 2. The core itself must be a DEBIT. "A debit vertical, part-financed" is
    #    the strategy being modelled; a credit core is a different animal.
    candidates = [c for c in candidates if net_price(c[:2]) > 0]
    if not candidates:
        return None, []

    # 3. Prefer the largest net debit — the biggest premium outlay is the
    #    position; anything smaller is what was sold against it.
    candidates.sort(key=lambda c: net_price(c[:2]), reverse=True)
    if len(candidates) > 1 and (net_price(candidates[0][:2])
                                == net_price(candidates[1][:2])):
        return None, []          # 4. a genuine tie is undecidable
    a, b, overlays = candidates[0]
    return (a, b), overlays


def core_structure(legs: list[Leg]) -> str | None:
    """Canonical structure of the group's core vertical, or None if undecidable."""
    core, _overlays = decompose_core(legs)
    if core is None:
        return None
    a, b = core
    debit_credit = "debit" if net_price(core) > 0 else "credit"
    return _vertical_label(a, b, debit_credit)


def _core_strikes(legs: list[Leg]) -> set:
    """Strikes of the core pair ONLY.

    Distinct from the whole group's strikes, which on a 3-leg group yield
    {110, 135, 150} — never equal to a `bull call spread 110/135` play's
    {110, 135}.
    """
    core, _overlays = decompose_core(legs)
    if core is None:
        return set()
    return {core[0].strike, core[1].strike}


# --------------------------------------------------------------------------
# Analysis-play parsing
# --------------------------------------------------------------------------
def play_structure(play_text: str) -> str:
    # canonical_spread_names first, for the same reason the backtest classifier
    # calls it: 'bear put debit spread' matches none of the keys below and used
    # to return "unknown", so a play the operator actually traded could not be
    # matched to its fill at all. lib/structure_names.py is the one encoding.
    t = canonical_spread_names(str(play_text)).lower()
    for key in ["bull call spread", "bear call spread", "bull put spread",
                "bear put spread"]:
        if key in t:
            return key.replace(" ", "_")
    if "protective put spread" in t or "put spread" in t:
        return "bear_put_spread"  # protective put spread == long put spread == bear_put debit
    if "call spread" in t:
        return "bull_call_spread"
    if "long call" in t:
        return "long_call"
    if "long put" in t:
        return "long_put"
    return "unknown"


def play_strikes(play_text: str):
    m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", str(play_text))
    if m:
        return {float(m.group(1)), float(m.group(2))}
    return set()


def play_dte(play_text: str, horizon):
    """Best-effort DTE proxy from the play text; falls back to horizon column."""
    t = str(play_text)
    # patterns like "45-60 DTE", "45–60 DTE", "~60 DTE", "90-127 DTE"
    m = re.search(r"(\d{1,3})\s*[-–]\s*(\d{1,3})\s*DTE", t)
    if m:
        return (int(m.group(1)) + int(m.group(2))) / 2.0
    m = re.search(r"~?\s*(\d{1,3})\s*DTE", t)
    if m:
        return float(m.group(1))
    try:
        return float(horizon)
    except (TypeError, ValueError):
        return np.nan


def play_dte_range(play_text: str, horizon):
    """`(lo, hi)` DTE from the play text, or None when nothing parses.

    Same three patterns as `play_dte`, kept SEPARATE on purpose: `play_dte`'s
    scalar (midpoint) contract feeds the §3 tier geometry gate and its callers
    depend on it. This range form exists for the deploy card's exit-by
    projection, where collapsing "45–60 DTE" to 52.5 would print a fabricated
    date. A scalar play returns (v, v).
    """
    t = str(play_text)
    m = re.search(r"(\d{1,3})\s*[-–]\s*(\d{1,3})\s*DTE", t)
    if m:
        lo, hi = sorted((int(m.group(1)), int(m.group(2))))
        return float(lo), float(hi)
    m = re.search(r"~?\s*(\d{1,3})\s*DTE", t)
    if m:
        v = float(m.group(1))
        return v, v
    try:
        v = float(horizon)
    except (TypeError, ValueError):
        return None
    if v != v:  # NaN horizon
        return None
    return v, v


SIDE = {"bull_call_spread": "debit", "bear_put_spread": "debit", "long_call": "debit",
        "long_put": "debit", "bull_put_spread": "credit", "bear_call_spread": "credit",
        "short_put": "credit", "short_call": "credit"}

# Directional bias, independent of debit/credit side. A family match on SIDE
# alone is direction-blind (e.g. long_put vs bull_call_spread are both
# "debit" but opposite bets) -- the family/substitution branch in map_entry()
# must require DIRECTION agreement too, not just SIDE agreement.
DIRECTION = {"bull_call_spread": "bullish", "long_call": "bullish",
             "bull_put_spread": "bullish", "short_put": "bullish",
             "bear_put_spread": "bearish", "long_put": "bearish",
             "bear_call_spread": "bearish", "short_call": "bearish"}


# --------------------------------------------------------------------------
# Deployment-ladder tier (encodes docs/deployment-rules.md)
# --------------------------------------------------------------------------
def ladder_tier(structure: str, market_regime: str, dte_proxy=np.nan, short_leg_delta=None):
    """Return (tier, partial_flag, reason). Tiers from deployment-rules.md.

    `short_leg_delta` is the optional 4th parameter for the bull_put_spread
    Tier-B clause in deployment-rules.md §3: short-leg
    ``0.08 <= |delta| <= 0.20`` AND ``DTE <= 59`` are BOTH required to hold
    Tier B; missing either drops the play to Tier C.

    - `short_leg_delta is None` (default): delta is unavailable, exactly as
      before this parameter existed. Behaviour is BYTE-IDENTICAL to the
      original function: only the DTE proxy is checked, the result is always
      `partial=True`, and the reason string says the delta is UNVERIFIED.
      This is the path every existing caller (and the pinned tests in
      `tests/test_journal_mapping.py`) exercises today.
    - `short_leg_delta` given AND `dte_proxy` is usable (not NaN): both
      conditions are evaluated for real and `partial=False`. Tier B if both
      pass; otherwise Tier C, with the reason string naming which condition
      failed and quoting the delta.
    - `short_leg_delta` given but `dte_proxy` is NaN: DTE still cannot be
      checked even though delta can, so this returns Tier C with
      `partial=True` — an unknown DTE is never silently treated as passing.
    """
    reg = market_regime or ""
    side = SIDE.get(structure, None)
    has_bear = "BEAR" in reg
    has_hvol = "H-VOL" in reg
    has_range = "RANGE" in reg
    has_lvol = "L-VOL" in reg
    has_evol = "E-VOL" in reg

    # Step 1 vetoes
    if structure == "bear_call_spread":
        return "VETO", False, "bear_call_spread intake veto"
    if has_bear and has_hvol:
        return "VETO", False, "market regime BEAR + H-VOL"
    if side == "credit" and has_range and has_lvol:
        return "VETO", False, "credit play in RANGE + L-VOL"

    # Step 2 tiers
    if structure == "bull_call_spread" and (has_range or has_evol):
        return "A", False, "bull_call_spread in RANGE/E-VOL"
    if structure == "bull_call_spread":
        return "B", False, "other bull_call_spread"
    if structure == "bull_put_spread":
        if short_leg_delta is None:
            # delta unknown; DTE proxy only -> PARTIAL (unchanged behaviour)
            if pd.notna(dte_proxy) and dte_proxy <= 59:
                return "B", True, f"bull_put DTE proxy {dte_proxy:g}<=59 (delta UNVERIFIED)"
            return "C", True, f"bull_put DTE proxy {dte_proxy} (delta UNVERIFIED)"
        # real delta supplied -> verify both conditions instead of proxying
        abs_delta = abs(short_leg_delta)
        if pd.isna(dte_proxy):
            return ("C", True,
                    f"bull_put delta {abs_delta:g} verified but DTE proxy UNKNOWN (NaN)")
        delta_ok = 0.08 <= abs_delta <= 0.20
        dte_ok = dte_proxy <= 59
        if delta_ok and dte_ok:
            return ("B", False,
                    f"bull_put delta {abs_delta:g} in [0.08,0.20] and DTE {dte_proxy:g}<=59")
        if not delta_ok and not dte_ok:
            return ("C", False,
                    f"bull_put delta {abs_delta:g} outside [0.08,0.20] AND DTE {dte_proxy:g}>59")
        if not delta_ok:
            return ("C", False,
                    f"bull_put delta {abs_delta:g} outside [0.08,0.20] (DTE {dte_proxy:g} OK)")
        return ("C", False,
                f"bull_put DTE {dte_proxy:g}>59 (delta {abs_delta:g} OK)")
    return "C", False, "Tier-C residual (bear_put / other)"


# --------------------------------------------------------------------------
# Leg group <-> analysis-play matching
# --------------------------------------------------------------------------
# THE MATCH VOCABULARY, in descending strength. This tuple is the single
# definition — `scripts/journal/config.py::MATCH_CONFIDENCES` derives from it,
# and every tally that iterates it (s04a_report.py, s04b_page.py) counts what
# it lists, so a new category can never be added in one place and silently
# dropped from a count in another.
#
#   EXACT       traded the emitted play, at its strikes
#   STRUCTURE   traded the emitted play's structure, different strikes
#   CORE        traded the emitted play's structure as the CORE of a larger
#               position, with a short leg sold to finance it
#   SUBSTITUTED traded a DIFFERENT, same-side same-direction structure
#   OVERLAY     not a play attempt at all — a financing/carry leg sold against
#               a position already open. Excluded from the matched/unmatched
#               tally rather than counted as a miss.
#   NONE        no play on the ticker/date matched
CONFIDENCES = ("EXACT", "STRUCTURE", "CORE", "SUBSTITUTED", "OVERLAY", "NONE")

# Preference order when several plays exist for the same ticker/date: an
# EXACT or true STRUCTURE match must win over a CORE or SUBSTITUTED one
# whenever both are on offer, so ranking (not "first candidate found") decides
# `best`. A whole-group match is stronger evidence than a decomposed one.
_CONF_RANK = {"EXACT": 0, "STRUCTURE": 1, "CORE": 2, "SUBSTITUTED": 3}


def map_entry(structure: str, legs: list[Leg], sig, ticker: str, ac) -> dict:
    """Match one leg group to AnalysisClaude rows on the signal date `sig`.

    `structure` is the label `classify_structure()` gave the group and `legs`
    are the same (oriented) legs it named.
    """
    day = ac[(ac["date"] == sig) & (ac["ticker"] == ticker)]
    # `core_structure` is returned whether or not a play matched: it is what
    # `s02_reconcile.py` tiers a financed spread off, and an untiered position is
    # not something to leave to whether an analysis row happened to exist.
    core_struct = core_structure(legs) if legs else None
    out = {"confidence": "NONE", "ac_play": None, "ac_structure": None,
           "dte_proxy": np.nan, "core_structure": core_struct}
    if day.empty:
        return out
    live_struct = _live_to_canonical(structure)
    live_strikes = {lg.strike for lg in legs}
    core_strikes = _core_strikes(legs) if core_struct else set()
    best = None
    best_rank = (99, 99)
    for _, pr in day.iterrows():
        ps = play_structure(pr["play"])
        pk = play_strikes(pr["play"])
        if ps == live_struct and live_strikes and pk == live_strikes:
            cand_conf = "EXACT"
        elif ps == live_struct:
            cand_conf = "STRUCTURE"
        elif core_struct is not None and ps == core_struct:
            # The operator traded this play's structure as the CORE of a larger
            # position, financing it with a short leg the analysis never
            # proposed. Deliberately NOT promoted to EXACT even when the core's
            # strikes agree (`pk == core_strikes`): EXACT means the emitted play
            # was traded, and this is the emitted play plus something else.
            cand_conf = "CORE"
        elif (SIDE.get(ps) == SIDE.get(live_struct) and SIDE.get(ps) is not None
              and DIRECTION.get(ps) == DIRECTION.get(live_struct)
              and DIRECTION.get(ps) is not None):
            # same side + direction, different structure family -> the operator
            # substituted a naked leg for a spread (or vice versa). NOT the
            # emitted play, so this must never be tallied as a structure match.
            cand_conf = "SUBSTITUTED"
        else:
            # direction mismatch (or unrelated structures) -> not a candidate
            continue
        # Secondary key: among several plays that tie on confidence, prefer the
        # one whose strikes the trade actually used. It cannot change the
        # confidence (a CORE match stays CORE however well the strikes agree),
        # only WHICH play is reported as the one traded.
        strikes_agree = bool(pk) and pk == (core_strikes if cand_conf == "CORE"
                                            else live_strikes)
        rank = (_CONF_RANK[cand_conf], 0 if strikes_agree else 1)
        if rank < best_rank:
            best, best_rank = (pr, cand_conf, ps), rank
            if rank == (0, 0):
                break
    if best is None:
        # no structure/family/direction match but same ticker/date exists -> NONE
        return out
    pr, conf, ps = best
    out.update(confidence=conf, ac_play=str(pr["play"]).replace("\n", " "),
               ac_structure=ps, dte_proxy=play_dte(pr["play"], pr.get("horizon")))
    return out


def _live_to_canonical(struct: str) -> str:
    s = struct.lower()
    if "bull_call" in s:
        return "bull_call_spread"
    if "bear_call" in s:
        return "bear_call_spread"
    if "bull_put" in s:
        return "bull_put_spread"
    if "bear_put" in s:
        return "bear_put_spread"
    if "short put" in s:
        return "short_put"
    if "short call" in s:
        return "short_call"
    if "long call" in s:
        return "long_call"
    if "long put" in s:
        return "long_put"
    return "unknown"
