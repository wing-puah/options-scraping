"""Canonicalise the structure NAME a play's text uses. Pure; no I/O.

The analysis prompt asks for a canonical structure name (``bear put spread``),
but the model periodically writes the debit/credit qualifier INSIDE the name —
``bear put debit spread``, ``bull put credit spread``, ``call debit spread`` —
because the framework's own prose describes those structures that way. None of
those strings contain the canonical ``bear put spread`` / ``put spread``
substrings that the downstream keyword matchers key on, so a two-leg vertical
used to fall through to the single-leg branch and be priced as ONE long option
(``scripts/backtest/classify.py``) or fail to match a real fill at all
(``scripts/live_loop/mapping.py::play_structure`` → ``"unknown"``). It is the
silent-wrong case, not a skip: the row still gets written, with a
``structure``/``legs`` that contradict its own ``play`` text.

This is the ONE encoding of that rewrite. Both the backtest classifier and the
live-loop play parser call it, so the backtest and the daily/fortnightly match
can never disagree about what a play's text named.

The (option type, debit|credit) pair determines the vertical completely, so the
qualifier is what resolves the name — an explicit ``bull``/``bear`` word that
contradicts it is a model slip and loses.
"""

import logging
import re

log = logging.getLogger(__name__)

# "<bull|bear>? <call|put> <debit|credit> spread" and the reversed qualifier
# order ("debit put spread"). Both are shapes the model has actually emitted.
_QUALIFIED_SPREAD_RE = re.compile(
    r"\b(?:(bull|bear)\s+)?"
    r"(?:(call|put)\s+(debit|credit)|(debit|credit)\s+(call|put))"
    r"[\s-]+spread\b",
    re.IGNORECASE,
)

_CANONICAL = {
    ("call", "debit"): "bull call spread",
    ("call", "credit"): "bear call spread",
    ("put", "debit"): "bear put spread",
    ("put", "credit"): "bull put spread",
}


def _replace(m: re.Match) -> str:
    opt = (m.group(2) or m.group(5)).lower()
    qual = (m.group(3) or m.group(4)).lower()
    name = _CANONICAL[(opt, qual)]
    stated = (m.group(1) or "").lower()
    if stated and not name.startswith(stated):
        # e.g. "bull put debit spread" — incoherent. The type+qualifier pair is
        # the reliable half, so it wins; the disagreement is worth a log line
        # because it means the prompt's vocabulary rule was violated twice over.
        log.debug("contradictory spread name %r → %r", m.group(0), name)
    return name


def canonical_spread_names(text: str) -> str:
    """Rewrite qualifier-infixed vertical names to their canonical form.

    ``"bear put debit spread 350/320"`` → ``"bear put spread 350/320"``. Text
    with no such phrase is returned unchanged. Case of the surrounding text is
    preserved; the rewritten name itself is always lower-case, which every
    caller matches against a lower-cased string anyway.
    """
    return _QUALIFIED_SPREAD_RE.sub(_replace, text or "")
