"""① Selection — which plays are worth taking?

Mostly null. 0 of 496 bear subsets, 0 of 15 ML cells. Selection is not tunable
from the columns we have.

    regime_gap_reread.py    reference — the pooled-book baseline snapshot other
                            studies import verbatim. Argues nothing on purpose.
    mech_regime_recut.py    SHIPPED — a deterministic SPY/VIX regime label beats
                            the model's free-text one. `mech_cell` is a column.
    bear_position_study.py  null — bear_put is a selection problem; DEMOTE fires.
    bear_arm.py             SHIPPED (B2) — 0 of 496 subsets pass, but
                            `be_after: 0.50` on bear debit clears every gate.
    ml_combination.py       null — 0 of 15 model × strategy cells. Re-open on new
                            COLUMNS only, never on new models.
    v4_bridge.py            open — written before the data existed; refuses to
                            compare a book against itself until v4 rows land.

Verdicts are hand-written in `scripts/study_map/catalog.py`; the lines above are
a signpost, not the source of truth. Two studies here (`mech_regime_recut`,
`regime_gap_reread`) do their work at MODULE level, which is why the runner
reads docstrings with `ast` instead of importing.
"""
