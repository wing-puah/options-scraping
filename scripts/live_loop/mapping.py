"""
Shared, tier-neutral matching + deployment-ladder layer for the live loop.

This module holds the reusable pieces that both a fortnightly audit
(`scripts/live_loop/stage1_map_fills.py`) and the daily production pipeline
(`scripts/journal/`, built separately) need: turning a live-filled options
structure into a canonical family, matching it against an AnalysisClaude play
on its signal date, and reconstructing the deployment-ladder tier that play
would have received.

`ladder_tier()` is the ONLY encoding of `docs/deployment-rules.md` §1-§3 —
there must never be a second copy. Anything that needs to know a structure's
tier (live-fill audit, daily deployment, a future backtest reconciliation)
calls this function; do not re-derive the veto/tier rules inline elsewhere.

What is deliberately NOT here: contract-string parsing, IBKR-snapshot
loading, fill-to-position reconstruction, and report emission. Those are
specific to the hand-pasted MCP snapshot format `stage1_map_fills.py` reads
and stay there (`parse_contract`, `load_snapshot`, `reconstruct`, `emit`,
`main`). This module only knows about *entries* (already-reconstructed
combos of legs with resolved/unresolved identity) and *analysis rows* — it
has no opinion on where either came from.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from lib.structure_names import canonical_spread_names


# --------------------------------------------------------------------------
# Structure classification (live fills -> canonical structure labels)
# --------------------------------------------------------------------------
def classify_structure(entry, positions):
    """Return (structure_label, net_price, net_with_comm, status, note, is_overlay)."""
    legs = entry["legs"]
    # net price per share: BUY=+ (debit component), SELL=- (credit component)
    net = 0.0
    comm = 0.0
    for lg in legs:
        tr = lg["trade"]
        sgn = 1 if tr["side"] == "BUY" else -1
        net += sgn * float(tr["price"])
        comm += float(tr["commission"])
    net_with_comm = net + comm / 100.0  # commissions always cost -> raise debit / cut credit

    matched = [lg for lg in legs if lg["match"] is not None]
    all_matched = len(matched) == len(legs)
    status = "OPEN" if all_matched else "CLOSED"  # unmatched opening fills are round-trip closed
    debit_credit = "debit" if net > 0 else "credit"

    # -- single leg --
    if len(legs) == 1:
        lg = legs[0]
        tr = lg["trade"]
        side = "long" if tr["side"] == "BUY" else "short"
        if lg["match"] is not None:
            m = lg["match"]
            right = "call" if m["right"] == "C" else "put"
            label = f"single {side} {right}"
            # overlay = short single-expiry leg over a same-ticker spread at another expiry
            is_overlay = _is_overlay(m, positions)
            if is_overlay:
                label += " (overlay)"
            return label, net, net_with_comm, "OPEN", "", is_overlay
        else:
            right = "call/put UNKNOWN"
            return (f"single {side} option ({debit_credit}), strike/expiry UNKNOWN",
                    net, net_with_comm, "CLOSED",
                    "round-trip: opened then bought/sold back within window (no open position to pin identity)",
                    False)

    # -- two-leg combos --
    if len(legs) == 2 and all_matched:
        a, b = matched[0]["match"], matched[1]["match"]
        if a["expiry"] != b["expiry"]:
            return ("diagonal/calendar (mixed expiry)", net, net_with_comm, status,
                    "legs span two expiries — not a vertical", True)
        return _vertical_label(a, b, debit_credit), net, net_with_comm, status, "", False

    # -- two-leg combo, unmatched (closed) --
    if len(legs) == 2:
        return (f"2-leg vertical ({debit_credit}), strikes/right UNKNOWN",
                net, net_with_comm, "CLOSED",
                "both legs closed (no open position to pin identity); structure inferred from net sign only",
                False)

    return (f"{len(legs)}-leg combo ({debit_credit})", net, net_with_comm, status, "", False)


def _vertical_label(a, b, debit_credit):
    """Canonical name for a same-expiry two-leg pair, from its rights and signs.

    Extracted from `classify_structure`'s two-leg branch so the core of a
    multi-leg structure (see `decompose_core`) is named by the SAME rules a
    standalone vertical is. Two encodings of "what is a bull call spread" would
    let a financed spread and a plain one disagree about their own name.
    """
    rights = {a["right"], b["right"]}
    # sort by strike
    lo, hi = (a, b) if a["strike"] < b["strike"] else (b, a)
    lo_pos = lo["position"]  # <0 short, >0 long
    hi_pos = hi["position"]
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


def _is_overlay(matched_pos, positions):
    """A single short leg is an overlay if the same ticker has other open option
    legs at a different expiry (i.e. it sits on top of an existing spread)."""
    if matched_pos["position"] >= 0:
        return False
    sym = matched_pos["symbol"]
    others = [p for p in positions
              if p["is_option"] and p["symbol"] == sym and p is not matched_pos]
    return any(p["expiry"] != matched_pos["expiry"] for p in others)


def _leg_sign(lg):
    """+1/-1 for a leg's direction, from the fill side rather than the match.

    `trade.side` is present on every leg shape this module sees; `match.position`
    is not (see `decompose_core`'s precondition note), so the fill is the
    reliable source when both exist.
    """
    return 1 if lg["trade"]["side"] == "BUY" else -1


def decompose_core(entry):
    """Split a multi-leg entry into `(core_pair, overlay_legs)`, or `(None, [])`.

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

    A NOTE ON LEG SHAPE. Callers build `entry["legs"]` to several shapes — some
    carry only `{"strike": ...}` in `match`. Every field is read with `.get()`
    and a missing one makes the group undecidable, never an exception.
    """
    legs = entry.get("legs") or []
    if len(legs) < 3:
        return None, []
    for lg in legs:
        m = lg.get("match")
        if not m or any(m.get(k) is None
                        for k in ("expiry", "right", "strike", "position")):
            return None, []
        if not (lg.get("trade") or {}).get("side"):
            return None, []

    # Candidate cores: a same-expiry, same-right pair at different strikes with
    # opposite signs — the shape of every vertical.
    candidates = []
    for i in range(len(legs)):
        for j in range(i + 1, len(legs)):
            a, b = legs[i], legs[j]
            ma, mb = a["match"], b["match"]
            if ma["expiry"] != mb["expiry"] or ma["right"] != mb["right"]:
                continue
            if ma["strike"] == mb["strike"]:
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
    candidates = [c for c in candidates if _pair_net_price(c[0], c[1]) > 0]
    if not candidates:
        return None, []

    # 3. Prefer the largest net debit — the biggest premium outlay is the
    #    position; anything smaller is what was sold against it.
    candidates.sort(key=lambda c: _pair_net_price(c[0], c[1]), reverse=True)
    if len(candidates) > 1 and (_pair_net_price(*candidates[0][:2])
                                == _pair_net_price(*candidates[1][:2])):
        return None, []          # 4. a genuine tie is undecidable
    a, b, overlays = candidates[0]
    return (a, b), overlays


def core_structure(entry):
    """Canonical structure of `entry`'s core vertical, or None if undecidable."""
    core, _overlays = decompose_core(entry)
    if core is None:
        return None
    a, b = core
    debit_credit = "debit" if _pair_net_price(a, b) > 0 else "credit"
    return _vertical_label(a["match"], b["match"], debit_credit)


def _pair_net_price(a, b):
    return sum(_leg_sign(lg) * float(lg["trade"]["price"]) for lg in (a, b))


def _core_strikes(entry):
    """Strikes of the core pair ONLY.

    Distinct from `_live_strikes`, which pools every leg's strike — on a
    3-leg group that yields {110, 135, 150}, which can never equal a
    `bull call spread 110/135` play's {110, 135}.
    """
    core, _overlays = decompose_core(entry)
    if core is None:
        return set()
    return {core[0]["match"]["strike"], core[1]["match"]["strike"]}


def leg_desc(entry, structure, positions):
    parts = []
    for lg in entry["legs"]:
        tr = lg["trade"]
        if lg["match"] is not None:
            m = lg["match"]
            sgn = "+1" if m["position"] > 0 else "-1"
            parts.append(f"{m['symbol']} {m['expiry']} {m['strike']:g}{m['right']} {sgn} @ {tr['price']:g}")
        else:
            sgn = "+1" if tr["side"] == "BUY" else "-1"
            parts.append(f"{tr['symbol']} UNKNOWN {sgn} @ {tr['price']:g}")
    return " / ".join(parts)


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
      This is the path every existing caller (and the 38 pinned tests in
      `tests/test_live_loop.py`) exercises today.
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
# Entry <-> analysis-play matching
# --------------------------------------------------------------------------
# THE MATCH VOCABULARY, in descending strength. This tuple is the single
# definition — `scripts/journal/config.py::MATCH_CONFIDENCES` and
# `stage1_map_fills.py`'s tally both derive from it, so a new category can never
# be added in one place and silently dropped from a count in another.
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


def map_entry(inv_row, sig, ticker, ac):
    """Match a live entry to AnalysisClaude rows on the signal date."""
    day = ac[(ac["date"] == sig) & (ac["ticker"] == ticker)]
    # `core_structure` is returned whether or not a play matched: it is what
    # `s02_reconcile.py` tiers a financed spread off, and an untiered position is
    # not something to leave to whether an analysis row happened to exist.
    entry = inv_row.get("entry") if hasattr(inv_row, "get") else inv_row["entry"]
    core_struct = core_structure(entry) if entry else None
    out = {"confidence": "NONE", "ac_play": None, "ac_structure": None,
           "dte_proxy": np.nan, "core_structure": core_struct}
    if day.empty:
        return out
    live_struct = _live_to_canonical(inv_row["structure"])
    live_strikes = _live_strikes(inv_row)
    core_strikes = _core_strikes(entry) if core_struct else set()
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
        # no structure/family/direction match but same ticker/date exists -> NONE per brief
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


def _live_strikes(inv_row):
    strikes = set()
    for lg in inv_row["entry"]["legs"]:
        if lg["match"] is not None:
            strikes.add(lg["match"]["strike"])
    return strikes
