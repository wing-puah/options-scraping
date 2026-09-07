# exit_drawdown — errata

Companion to
[`pre-registrations/f2_management/exit_drawdown.md`](pre-registrations/f2_management/exit_drawdown.md).
`scripts/study_review/` discovers this file by convention and inlines it beside
the registration, so **read it as part of the authority the run is graded
against, not as commentary.**

**What it holds.** The registration is IMMUTABLE IN SUBSTANCE. It may be
consolidated editorially — a later reading folded into the section it amends, so
the file states one final design read top to bottom — and it has been. What
cannot be folded that way is here: a build-time resolution that changes what a
gate REFUSES, what an arm DOES, or how a clause is READ. Folding one of those
into the registration's own prose would present a decision taken while the
module was built as a commitment made before it, which is the one thing a
pre-registration exists to prevent.

**What it does not do.** It never relaxes a commitment. Every gate, bar, arm
definition, threshold, population, criterion and verdict token this file does
not explicitly resolve is graded against the registration as written. No number,
arm label, gate id, clause number or verdict token differs from the registration
here.

**A grading defect reopens the MODULE, never the registration.**

## Where each recorded reading lives

The module (`scripts/backtest_study/f2_management/exit_drawdown.py`), the graded
report (`backtests/study_output/exit_drawdown-*.txt`) and the two analyst
gradings cite these readings by their recorded labels. Every label resolves
here.

| Recorded as | What it fixes | Where it lives now |
|---|---|---|
| 2026-09-05 (build), reading 1 | G1's shift is one session of the rule's own grid | **Registration**, the G1 bullet under "Gates"; its 57-row measurement is in "Build notes" |
| 2026-09-05 (build), reading 2 — cited as "correction 2" | G1's DIRECTION half is read on ARM O's volume leg | **§1 below** |
| (a) of 2026-09-05 (build, second) | ARM P's ledger releases the reserve at the LATER half | **§2 below** |
| (b) of 2026-09-05 (build, second) | ARM D collapses to the MODAL block choice | **§3 below — SUPERSEDED by (f), recorded but not live** |
| (c) of 2026-09-05 (build, second) | ARM P's dollar drawdown is withheld by default | **Registration**, ARM P's STATUS bullet, and **§4 below** |
| (d) of 2026-09-05 (build, second) | clause 5 reads the sibling era's RECORDED cells | **§5 below**, narrowed by (i) |
| (e) of 2026-09-05 (build, second) | G1's CHANGE half is tallied per variant | **§6 below** |
| (f) of 2026-09-05 (build, third) | ARM D collapses to the EARLIEST block's choice | **§3 below** |
| (g) of 2026-09-05 (build, third) | clause 4's signless tier is read strictly | **Registration**, clause 4 under "Bar for a candidate" |
| (h) of 2026-09-05 (build, fourth) | G-CAL's parenthetical names the self-test | **§7 below** |
| (i) of 2026-09-05 (build, fourth) | clause 5's referent is the SECONDARY era's PRIMARY cell | **Registration**, clause 5; its sidecar mechanism is **§5 below** |

Readings 1, (g) and (i)'s referent rule were recorded while the module was
built, and have since been folded into the registration's own sections: each
narrows a clause the registration already carried without changing what it
refuses, so the registration can state it as design. The rest are here because
they cannot.

## 1. G1's DIRECTION half is read on ARM O's volume LEG, not on its conjunction

ARM O's volume variant fires on a volume spike **AND** a mark that closed
against the position. Only the volume half is governed by the series G1 shifts,
so delaying the volume while the mark stays put RE-PAIRS the two legs: a spike
that missed an adverse mark on its own session can land on one a session later,
ahead of the original firing. That is an artifact of shifting one leg of a
conjunction, not a rule reading the future, and a literal reading of G1 would
fail a correct rule for it. So for that variant alone, "no exit moves EARLIER"
is evaluated on the volume leg in isolation, and the conjunction's own
earlier-firings are PRINTED as a disclosed, non-gating count beside it. The
probe is pinned to the rule by a coherence check — the conjunction can only ever
fire at or after its own volume leg — and a non-zero coherence failure FAILS G1,
so the two cannot drift apart silently.

**This is a SCOPING of the registered gate, decided at build time, and it is
outcome-bearing.** G1 as registered asks that **no exit moves EARLIER** than the
original, with no variant carve-out, and a G1 failure is (V0): the run stops
non-zero and **NO token is emitted for any arm**. Read literally, the
conjunction's earlier-firings on the graded run would have voided it. They are
disclosed as a count instead, and the coherence check is what replaces the
literal reading. The ATR stop and the OI unwind are gated on both halves of G1
as registered.

## 2. ARM P: the ledger holds the WHOLE reserve until the LATER half exits

The registration models ARM P as **TWO synthetic `Pos` per rec** (half size
each, each with its own exit session), "so `book_curves` sees valid per-position
windows and **the ledger releases half the reserve at the FIRST exit**".
`account_sim.simulate()` carries ONE exit session per position and cannot
release half a reserve, and `simulate()` is not forked for this study — the whole
module is a composition around frozen machinery. So the LEDGER-facing blend
(`partial_replayer`) reports `days_held` as the LATER of the two halves and the
reserve is released then.

This is CONSERVATIVE against the registered release: holding a reserve longer
can only ever admit FEWER later positions, never more, so no ARM P number is
flattered by it. The CURVE is unaffected and sees the registered shape —
`split_positions()` re-splits every ARM P position into its two halves, each
with its own contract count and its own exit session, before `book_curves` is
called. The deviation is printed in ARM P's census.

The registered sentence stands as written; this records that the ledger does not
implement it and what it does instead.

## 3. ARM D's per-block choice collapses to the EARLIEST block's

ARM D's `d` is "chosen walk-forward exactly as every other threshold here is",
and the registration's binding rule is "Thresholds are chosen per walk-forward
block on TRAIN dates only … then applied to that block's TEST dates", with a
`date → block` map dispatching **each position's** configuration.
`Cfg.dd_throttle` is ONE value for a whole simulation — a ledger cannot carry a
different `d` per block — so ARM D provably cannot do that, and a sizing arm's
per-block selection must collapse before a stitched book can be run at all.

**(b), recorded first and SUPERSEDED — not live.** (b) resolved the collapse to
the MODAL block choice, framing that as "a property of the ledger, not a tuning
choice". **That framing was wrong, and the resolution with it.** WHICH value the
collapse lands on is not a property of the ledger; it is a choice, and the modal
one is LOOKAHEAD. A modal collapse replays block 0's TEST dates under a `d`
selected using blocks 1..n's fits, whose TRAIN sets contain dates at or after
those very test dates — so the stitched book would not be out of sample, and (b)
neither said so nor labelled the cell. It is not cosmetic either: on the v4
primary population one grid value throttles sessions and changes the book while
the other never fires, so the collapse decides the whole ARM D cell. The report
argues the live rule by contrast with (b), which is why (b) is recorded here
rather than deleted.

**(f), live.** The collapse is to the **EARLIEST block's choice**, which uses no
information after its own TRAIN window and gives the stitched ARM D book the
same out-of-sample guarantee every exit arm's per-block dispatch gives. Block
indices are unique, so there is no tie to break. The disclosure (b) committed is
kept in full and unchanged: the per-block selection table prints what each block
picked, the collapse is printed with the collapsed value named, and **every grid
value's own stitched OOS book is printed beside it**. The collapse rule lives in
one function (`collapse_choice()`, called by `run_book()`), so no caller can
perform a different one while the report's prose describes this one. ARM D
remains SECONDARY and unshippable from this family.

This is an EXCEPTION to the per-block dispatch rule, forced by the ledger and
found while the module was built. That rule's text is untouched; ARM D alone
runs one collapsed value, and no exit arm does.

## 4. ARM P's account-level drawdown is WITHHELD in dollars by default

The registration scopes the plan's dollars ban to ARM P's per-row and paired
comparison, reports the account-level drawdown in dollars for ARM P as for every
other arm, and then carries that scoping as an OPEN ITEM requiring **"an
explicit operator ACK before the module is built"** — stating the ALTERNATIVE
reading, no dollar drawdown figure for ARM P with the co-primary quoted in R and
as a percentage of starting capital, for the case where the operator reads the
ban as unscoped.

**STATUS: OPEN. No operator ACK is recorded, so the module runs the ALTERNATIVE
reading as its DEFAULT.** ARM P's account-level max drawdown, its improvement
and the improvement's block-bootstrap CI bounds are all printed as a share of
starting capital, with a banner naming the open item; `--arm-p-dollars` prints
the dollar levels for whoever holds the ack. **The verdict is identical either
way** — clause 1 is evaluated on the improvement RATIO, which is scale-free — so
this resolves the PRESENTATION and defers, rather than pre-empts, the operator's
choice. When the ack is given for the SCOPED reading, the flag becomes the
default and this status is edited to record it; the ack is never retro-fitted by
report prose.

## 5. Clause 5's referent: the sidecar the two eras exchange

Clause 5's referent is the SECONDARY era's PRIMARY cell — that reading is in the
registration. Its mechanism is here.

The two eras are two separate processes, so each run records its own cells
(verdict, improvement ratio, power) in a per-era sidecar under
`backtests/study_output/` and reads the SECONDARY era's if one is on disk. The
sidecar names BOTH its era and its population, only the PRIMARY cut writes one,
and a sidecar that names another era, another population, or none at all is
REFUSED — a v3 `all` run's sidecar read as v4 PRIMARY's clause-5 referent would
cross two cuts exactly as a stale filename would cross two eras.

**An absent or refused referent is VACUOUS.** When the v3 run has not been
recorded, or its sidecar is refused, clause 5 is VACUOUS and printed with the
reason — the same disclosure the registration fixes for a v3 cell with no sign,
and for the same reason: a population that has not spoken contradicts nothing. A
recorded, POWERED, opposite-signed v3 PRIMARY cell FAILS the clause and blocks
the candidate, which is the behaviour the clause was written for and which a
hardcoded pass could not deliver.

**Note the widening, and read it as such.** The registration's own vacuous case
is a v3 cell that RAN and had no sign — it commits that v3 "is RUN and
REPORTED". Treating an unrun or refused sidecar as vacuous extends a criterion
pass to an artifact-level failure, which the registered grammar would otherwise
route through machinery. It is recorded here rather than folded for that reason.

The no-OOS path records its cells BEFORE returning: a v3 primary population with
no surviving test block must not leave NO sidecar, or v4's clause 5 would read
VACUOUS for a reason that had nothing to do with v3's evidence. An
all-UNDERPOWERED sidecar is the honest referent there — cells with no sign, read
as vacuous-but-disclosed, with the file named rather than absent.

## 6. G1's "at least one exit CHANGED" half is tallied PER VARIANT

The gate's stated purpose for that half is per-series — "the first half proves
the series is actually being read". One counter aggregated over every exercised
variant lets a series that is in fact never read (a wiring bug returning an
empty map) hide behind a variant whose series does change, so each EXERCISED
variant must change at least one firing session on its own and the per-variant
table is printed. The gate's series are also read through the SAME loaders the
arms are wired to, so it probes what the run reads rather than a parallel read
of the same files.

**This is STRICTER than the registered gate**, which asks for one run-level
assertion that **at least one exit changes**. It tightens what G1 refuses and
weakens nothing, but it was decided while the module was built and is not a
pre-commitment: a variant that exercises no rows is reported NOT EXERCISED
rather than failing the gate.

## 7. G-CAL's parenthetical names the SELF-TEST invocation, which is the opposite of the check

G-CAL reads: "`account_sim`'s own gates **G2–G5** must still pass with the
DEFAULT replayer (`account_sim --selftest-gates`)." The requirement — G2–G5
passing under the default replayer — is exactly right; the parenthetical is not
the command that shows it, and it stands in the registration as the erroneous
citation it is. `--selftest-gates` deliberately INVERTS every one of those
gates' expectations (it adds 1 to `days_held` in G2, injects a \$1 leak into
G3's identity, and inverts G4's and G5's comparisons) so that a healthy build
must print `GATES: FAILED`. It is a check on the CHECKER, not the check, and a
run of it that PASSED would mean the gates were broken.

The registered gate is therefore read as: **`account_sim.run_gates` under its
DEFAULT (non-self-test) path, on the population this study deploys through, run
IN THIS PROCESS, with its per-gate PASS/FAIL lines printed inside this study's
own report; a failure fails G-CAL exactly as a `book_signature` mismatch does.**
`run_gates` is CALLED, never copied: G2's calibration identity, G3's ledger
accounting, G4's selection identity and G5's outcome-blindness are
`account_sim`'s properties, and a second implementation of them here is how a
study and its host come to certify different things.

**The printing requirement is this reading's addition, not the registered
gate's.** The first build delegated the half to a separate `--selftest-gates`
invocation "outside this process" and printed no G2–G5 result at all, so the
report ASSERTED a gate whose outcome it did not carry — the two analysts split
on it precisely there (one graded G-CAL MET on the narrower printed claim, one
declined to grade it at all), which is what an un-carried sub-check does to a
reader. A grader reading the registration alone would find no requirement that
the lines be printed; a grader reading this file finds one.
