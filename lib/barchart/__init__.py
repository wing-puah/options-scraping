"""Barchart scrapers and feed parsers.

Only true scrape/parse modules live here (session, options, iv_history, underlying,
corporate_actions). The pure-logic modules that merely *consume* Barchart data —
``lib.iv_history`` (IV-percentile enrichment), ``lib.counterpart_iv``,
``lib.price_catalyst`` — stay in ``lib/``.

``BarchartSession`` is re-exported so ``from lib.barchart import BarchartSession``
keeps working; submodules are imported by their full path
(``from lib.barchart.options import ...``).
"""
from lib.barchart.session import BarchartSession

__all__ = ["BarchartSession"]
