"""⑤ Hedging — what protects the book when the ladder is wrong?

One ship and three open questions. The ladder picks and sizes; this family asks
what is held ALONGSIDE it, and every answer after the first is blocked on dates
or underpowered.

    bear_deploy.py      SHIPPED — bear selection is unfixable, but bear pays on
                        the deployed book's worst dates (correlation −0.13), and
                        picking bear by |delta| DESCENDING was adopted. Bear is
                        a hedge, not a selection. It is also the ORIGIN of the
                        shared contribution and sizing rules now in
                        `../lib/hedge_criteria.py`.
    calendar_hedge.py   open — the vol sleeve's one survivor, the calendar,
                        re-derived under a pre-registered pick rule and a strict
                        fill rule. Every gate passes and R4 reproduces exactly,
                        then H2 is underpowered at n=6. Blocked on new dates,
                        not refuted.
    hedge_timing.py     open · 0 of 9 TIMING-CANDIDATE survivors — can a
                        discretionary hedge trigger (chop, a SPY gap-up, a SPY
                        down-run) be made mechanical? The gap-up arms came back
                        CONTRARY, which is what the §4 prohibition the operator
                        accepted on 2026-09-06 rests on. The operator's own
                        streak trigger stays UNDERPOWERED by design.
    hedge_exposure.py   open · UNDERPOWERED on the mechanism, MEASUREMENT-ONLY on
                        ARM M — when the book is concentrated in one correlated
                        cluster, does a put on that cluster's proxy cut its
                        mark-to-market drawdown? No hedge cell powers. Carries
                        the `--admitted` ARM since 2026-09-07: the same question
                        on the book `account_sim` actually takes, which was
                        `hedge_concentration.py` until that module was merged in
                        and deleted. Stage 1 there is a POWERED
                        PRECONDITION-NULL, so Stage 2 never opened. Run it with
                        `run hedge_exposure -- --admitted`; a bare run does both
                        arms, and the admitted arm files under
                        `hedge_exposure-admitted`.

Read `bear_deploy` first: it is the only ship here, and the other three are its
surviving questions — with what, when, and how much.

    vol_sleeve.py       DELETED 2026-09-07 — null · CLOSED. The straddle cleared
                        its gate then died ex-window, and its correlation with
                        the deployed book was the WRONG SIGN: it re-wrapped the
                        same exposure. Only the calendar survived, and it went to
                        `calendar_hedge`, which rebuilds that cell in-process
                        under R4. The verdict is the DELETED row in
                        research/study-map.md; the per-era record is
                        research/study-results/f5_hedging/vol_sleeve.md; the
                        synthesis layer R4 still runs is lib/sleeve_synth.py.
    hedge_concentration.py
                        DELETED 2026-09-07 — merged into `hedge_exposure.py` as
                        its `--admitted` arm rather than retired: the question
                        was live, the module was a second copy of the same
                        machinery. Its two-stage verdict is unchanged by the
                        merge. The verdict is the DELETED row in
                        research/study-map.md; the per-era record is
                        research/study-results/f5_hedging/hedge_concentration.md.

The family was split out of `f3_structure/` and `f4_deployment/` on 2026-09-08.
Nothing about any study changed — the four hedge modules were filed under the
question they happened to be asked next to, and the hedge programme is a
question of its own. Verdicts are hand-written in `scripts/study_map/catalog.py`;
the lines above are a signpost, not the source of truth.
"""
