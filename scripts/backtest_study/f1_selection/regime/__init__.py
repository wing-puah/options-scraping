"""① Selection / regime — does the market state or its timing change which plays work?

    regime_gap_reread.py    reference — the pooled-book baseline snapshot other
                            studies import verbatim. Argues nothing on purpose.
    mech_regime_recut.py    SHIPPED — a deterministic SPY/VIX regime label beats
                            the model's free-text one. `mech_cell` is a column.
    macro_event_study.py    scheduled macro events (FOMC, CPI, NFP) against the book.
    dip_buy.py              do Tier A/B positions do better after SPY closes below its 50-day SMA?
    adaptive_ladder.py      does re-choosing the selection rule from trailing results beat the ladder?
    regime_map.py           each ladder tier against each market label: where does it make or lose money?
    regime_confirm.py       does a mech BEAR flip that persists, with stress signs agreeing, predict a 10% fall?

`mech_regime_recut` and `regime_gap_reread` do their work at MODULE level, which
is why the runner reads docstrings with `ast` instead of importing.
"""
