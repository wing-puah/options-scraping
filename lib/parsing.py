"""Shared numeric-cell parsing for Barchart-style data.

`to_float` is the single home for what used to be a `_to_float` helper copied
into half a dozen modules (barchart_options, barchart_iv_history, corporate_actions,
price_catalyst, flow_summary). It tolerates the punctuation and sentinel strings
Barchart feeds emit.
"""
from __future__ import annotations

# Strings that mean "no value" once punctuation is stripped (compared lower-cased).
_SENTINELS = {"-", "n/a", "na", "null", "none", "unch"}


def to_float(value, default=None):
    """Parse a Barchart numeric cell to float, else ``default``.

    Strips thousands commas and ``$``/``%``; bare int/float pass through; empty
    string or a sentinel (``-``, ``n/a``, ``na``, ``null``, ``none``, ``unch``)
    returns ``default``.
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if s == "" or s.lower() in _SENTINELS:
        return default
    try:
        return float(s)
    except ValueError:
        return default
