"""② Management — when do I get out?

Where the edge actually is. Both shipped exit rules came from here.

    exit_mechanism_study.py         SHIPPED — the original grid; the production
                                    debit profile (target 0.90, stop 0.75, time
                                    exit at 0.75 DTE, no trail) is this study.
    combined_exit_study.py          reference · RETIRED — same grid on a bigger
                                    tuning set; showed exits are regime-
                                    conditional, which motivated the two
                                    switch studies below.
    underlying_exit_study.py        null · RETIRED — stop credit spreads on the
                                    UNDERLYING instead of the mark. Nothing.
    exit_switch_mech_study.py       SHIPPED — the BEAR_HE cell (trail 0.50 at
                                    trigger 0.50). L-VOL and RANGE/BULL stay
                                    gated and commented out in backtest.yml.
    exit_switch_structure_study.py  reference — the GUARD on that shipped rule,
                                    catching the composition trap that killed
                                    oi_confirm_pct and iv_pct.
    bear_giveback.py                null — the `be_after` grid ships nothing
                                    beyond what is live; the give-back pattern
                                    lives in the UNDERLYING, not the mark.
    volume_signal.py                null — share volume is liquidity in a
                                    costume. Column closed.
    next_day_move.py                null — ARM C does not clear the confound.

RETIRED means the inputs are gone for good, not that the verdict is void: the
runner still runs one by explicit name, `run --all` skips it with a notice, and
`scripts/study_map/catalog.py` records both the verdict and where it was logged.
"""
