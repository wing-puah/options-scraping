"""④ Deployment — can I actually run this?

Feasibility, not edge. Delta-notional binds before cash does. NOTHING ships from
this family under any outcome: it asks whether the ladder the other three
families built is runnable in a real account, not whether it is right.

    bear_deploy.py      SHIPPED — bear selection is unfixable, but bear pays on
                        the deployed book's worst dates (correlation −0.13), and
                        picking bear by |delta| DESCENDING was adopted. Bear is
                        a hedge, not a selection.
    account_sim.py      open — a real $25,000 account paying for positions,
                        holding reserve, respecting a delta cap. The caps
                        survive; the WINDOW does not. Config-driven and
                        stateless: `config/account-sim.yml` IS the simulation.
                        Its arms (`--compounding`, `--structure-universe`,
                        `--live-select`) each file under their own report stem.
    selection_order.py  open · UNDERPOWERED at G0 — each re-ordering changes
                        only 7–14% of the deployed book, so the best-powered arm
                        reaches 11 affected dates against a floor of 25 declared
                        before the count was knowable. Census only.
    portfolio_delta.py  open · CANDIDATE-FOR-INDEPENDENT-WINDOW — is the book's
                        net delta LEVEL a lever? On v4 only `B ceiling 1.00`
                        clears the seven-part conjunction and the 1.50 ceiling
                        drops out. The label queues an independent window and
                        nothing else; no ceiling may be adopted on its P&L.
    concurrency_correlation.py
                        open · NOISE — nothing caps the STOCK of open positions,
                        so does the size or internal similarity of the open book
                        degrade per-position outcome? All 11 powered arms sit
                        inside the random-admission null band, in both eras.
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
                        `hedge_exposure-admitted`. Verdicts for the deleted
                        module are the DELETED row in research/study-map.md.

`account_sim`'s `--live-select` arm is the one sanctioned research→production
import in the package; it lives in `../lib/live_select.py` because it carries no
verdict of its own. The hedge programme's shared contribution and sizing rules
live in `../lib/hedge_criteria.py`, with `bear_deploy` as their origin; a study
keeps its own registered grid and report shape on top.
"""
