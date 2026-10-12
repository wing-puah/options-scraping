"""① Selection — which plays are worth taking?

Mostly null. 0 of 496 bear subsets, 0 of 15 ML cells. Selection is not tunable
from the columns we have.

    regime/     market state and timing — mech_regime_recut (SHIPPED), regime_gap_reread
                (reference baseline), macro_event_study, dip_buy, adaptive_ladder, regime_map
    bear/       bear_position_study (null), bear_arm (SHIPPED, B2)
    signal/     what the analysis emits — ml_combination (null), text_features, prompt_eval,
                trigger_entry, emission_timing, direction_hit (null)
    benchmark/  yardsticks — ticker_class, mechanical_benchmark, v4_bridge (open)

Each group's own `__init__.py` lists its studies and verdicts.

Verdicts are hand-written in `scripts/study_map/catalog.py`; the lines above are
a signpost, not the source of truth. Two studies in `regime/` (`mech_regime_recut`,
`regime_gap_reread`) do their work at MODULE level, which is why the runner
reads docstrings with `ast` instead of importing.
"""
