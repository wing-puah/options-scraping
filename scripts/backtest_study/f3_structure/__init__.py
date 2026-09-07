"""③ Structure — am I expressing the signal in the wrong wrapper?

One +0.085 effect that does not hold out of sample, and one survivor that is
underpowered rather than refuted.

    bear_rewrap.py      null — a bear SPREAD sells away the vol expansion that
                        makes a bear position pay. Dropping the short leg is
                        worth +0.085 and does NOT hold in 2026.
    calendar_hedge.py   open — the vol sleeve's one survivor, the calendar,
                        re-derived under a pre-registered pick rule and a strict
                        fill rule. Every gate passes and R4 reproduces exactly,
                        then H2 is underpowered at n=6. Blocked on new dates,
                        not refuted.
    financed_spread.py  null on same-expiry shapes, and on v4 its same-direction
                        financed vertical prints RE-WRAP: a real gain that is the
                        book's own exposure again, so it fails the anti-re-wrap
                        clause it was registered against. Nothing ships.

Read `bear_rewrap` then `calendar_hedge`: each is the previous one's surviving
question.

    vol_sleeve.py       DELETED 2026-09-07 — null · CLOSED. The straddle cleared
                        its gate then died ex-window, and its correlation with
                        the deployed book was the WRONG SIGN: it re-wrapped the
                        same exposure. Only the calendar survived, and it went to
                        `calendar_hedge`, which rebuilds that cell in-process
                        under R4. The verdict is the DELETED row in
                        research/study-map.md; the per-era record is
                        research/study-results/f3_structure/vol_sleeve.md; the
                        synthesis layer R4 still runs is lib/sleeve_synth.py.
"""
