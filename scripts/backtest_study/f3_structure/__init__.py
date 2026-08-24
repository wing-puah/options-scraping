"""③ Structure — am I expressing the signal in the wrong wrapper?

One +0.085 effect that does not hold out of sample, and one survivor that is
underpowered rather than refuted.

    bear_rewrap.py     null — a bear SPREAD sells away the vol expansion that
                       makes a bear position pay. Dropping the short leg is
                       worth +0.085 and does NOT hold in 2026.
    vol_sleeve.py      null · CLOSED — the straddle clears its gate then dies
                       ex-window, and its correlation with the deployed book is
                       the WRONG SIGN: it re-wraps the same exposure. Only the
                       calendar survived, and went to `calendar_hedge`.
    calendar_hedge.py  open — that one survivor re-derived under a pre-registered
                       pick rule and a strict fill rule. Every gate passes and R4
                       reproduces exactly, then H2 is underpowered at n=6. Blocked on
                       new dates, not refuted.

Read them in that order: each one is the previous one's surviving question.
"""
