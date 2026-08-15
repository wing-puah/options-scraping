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
    selection_order.py  open · POWER-STOPPED at G0 — each re-ordering changes
                        only 7–14% of the deployed book, so the best-powered arm
                        reaches 11 affected dates against a floor of 25 declared
                        before the count was knowable. Census only.

`account_sim`'s `--live-select` arm is the one sanctioned research→production
import in the package; it lives in `../lib/live_select.py` because it carries no
verdict of its own.
"""
