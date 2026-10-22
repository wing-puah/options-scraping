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
    index_vrp.py        NO-TAIL-LINK — a monthly short SPY iron condor on real
                        cached quotes neither loses with the ladder book's worst
                        sessions nor cushions them clearly (2026-10-12). Nothing ships.
    earnings_vol.py     NULL on both arms (2026-10-13) — a long ATM straddle and a
                        long ATM double calendar across 25 names' earnings. The
                        calendar's +0.073 mean misses its season-clustered CI and
                        turns CONTRARY at the natural fill. Neither moves with the
                        book. Nothing ships.
    structure_sweep.py  registered 2026-10-22, accepted by default — eight structures
                        on the same 2026 plays, Holm across seven graded arms, and
                        a second sample that awaits a fetch. Not yet graded.

`hedge_structure.py` was here until 2026-09-08 and is now in `../f5_hedging/`,
with the rest of the hedge programme. So was the DELETED `vol_sleeve.py`, whose
registration and record were deleted 2026-09-08 (git 44bbfb2).
"""
