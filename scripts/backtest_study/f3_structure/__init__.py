"""③ Structure — am I expressing the signal in the wrong wrapper?

One +0.085 effect that does not hold out of sample, and one shape that reads as
the book's own exposure again.

    bear_rewrap.py      null — a bear SPREAD sells away the vol expansion that
                        makes a bear position pay. Dropping the short leg is
                        worth +0.085 and does NOT hold in 2026.
    financed_spread.py  null on same-expiry shapes, and on v4 its same-direction
                        financed vertical prints RE-WRAP: a real gain that is the
                        book's own exposure again, so it fails the anti-re-wrap
                        clause it was registered against. Nothing ships.

`calendar_hedge.py` was here until 2026-09-08 and is now in `../f5_hedging/`,
with the rest of the hedge programme. So is the DELETED `vol_sleeve.py`, whose
frozen record moved with it.
"""
