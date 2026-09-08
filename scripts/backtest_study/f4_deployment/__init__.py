"""④ Deployment — can I actually run this?

Feasibility, not edge. Delta-notional binds before cash does. NOTHING ships from
this family under any outcome: it asks whether the ladder the other families
built is runnable in a real account, not whether it is right.

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

`account_sim`'s `--live-select` arm is the one sanctioned research→production
import in the package; it lives in `../lib/live_select.py` because it carries no
verdict of its own.

`bear_deploy.py`, `hedge_timing.py` and `hedge_exposure.py` were here until
2026-09-08 and are now in `../f5_hedging/`, with the rest of the hedge
programme. So is the DELETED `hedge_concentration.py`, whose frozen record moved
with it. The shared contribution and sizing rules those studies lean on stay in
`../lib/hedge_criteria.py`.
"""
