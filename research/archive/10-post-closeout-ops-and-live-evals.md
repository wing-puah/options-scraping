# Archive 10 — 2026-08-12: rules split, v4 bridge deviation, live loop, live-vs-analysis evals

_Status: historical (covers 2026-08-12). Superseded / qualified by: [next-steps.md §2.2](../next-steps.md) — the v4-bridge deviation recorded here has RESOLVED: the study ran 2026-08-24 and 2026-08-27 and prints `VERDICT: LADDER UNVALIDATED ON v4` (four of five tests shift), so the "interim posture: deploy under v3 rules" is now the standing instruction, not an interim one; [archive/15 §2026-08-15 structure-name defect](15-era-scoping-suite-repair-and-selection-order.md) — the live-loop `play_structure` parser returned `unknown` for `bear put debit spread`, so the Stage-1 mapping tallies quoted here undercount matches (fixed in `lib/structure_names.py`). The rules split, the v1→v2→v3 null and the operator-card reference stats all stand. Live record: [current.md](../current.md)._

Covers the operational 2026-08-12 work: the deployment-rules split
(operator card vs evidence file), the v4 bridge RECORDED DEVIATION,
the live loop promoted to tracked code, the v1 → v2 → v3
prompt-version comparison with the June-2026 live-vs-analysis audit,
the Stage 1 live-vs-tier eval on July, and the deployment reference
stats added to the operator card.
See [../README.md](../README.md) for the full section index.

---

## 2026-08-12 — deployment rules split: operator card vs evidence

`docs/deployment-rules.md` had grown to 284 lines by accretion — every study
that shipped a rule appended its derivation, CIs, LOO folds, limits and rollback
trigger to the same file, so the ~15 things an operator actually does at deploy
time were interleaved with ~200 lines of research record. With v3 tuning closed,
the rules have stopped churning and the doc is stable enough to freeze.

- **`docs/deployment-rules.md`** → instructions only, ~110 lines, as a
  deploy-day sequence: before-you-deploy → VETO → tier → order-entry geometry →
  hedge sleeve → exits → what not to use.
- **`research/deployment-evidence.md`** (new) → everything else,
  moved with the numbers intact. Nothing was dropped; the diff is a move.

**Three defects fixed in passing, all found by reading the doc against the code:**

1. **Stale command.** The card told the operator to run
   `python3 backtests/mech_regime/fetch_spy_vix.py --full`. That path is
   untracked scratch — the tracked fetcher has been
   `scripts/collector/fetch_mech_regime.py` since the mech-regime move, and
   `make analyze` already depends on the `mech-regime` target. Now just
   `make analyze`.
2. **Hand-computed regime label.** The card still spelled out "SPY < 50-day SMA
   and 20-day return < 0" as an operator step. `mech_cell` has been a
   `ROW_COLUMNS` field and backfilled across the analysis tabs since the 08-11
   addendum — the card now says *read the column*, and the definition moves to
   the evidence file as reference. This was a live opportunity to mislabel a
   date by hand.
3. **Exit rules split across three sections.** "Preconditions", "Exit
   management" and "Bear debit spreads — breakeven ratchet" each held part of
   the exit config, so setting up an order meant reading all three and
   reconciling the BEAR_HE suppression clause yourself. Now one four-row table
   (debit normal / debit BEAR_HE / bear debit / credit) with the suppression as
   an explicit footnote.

The `## Exit management` heading is **preserved verbatim** — six places link to
`deployment-rules.md §"Exit management"` (`docs/backtest-reference.md`,
`scripts/backfill_mech_cell.py`, `scripts/collector/fetch_mech_regime.py`,
`scripts/analysis_pipeline/config.py`, `scripts/analysis_pipeline/core.py`,
`.github/workflows/backfill-mech-cell.yml`), and keeping the heading is cheaper
than updating six references.

**The three open rollback triggers are now in one table** in the evidence file
rather than scattered across three sections — BEAR_HE trail (≥25 new affected
dates), bear-debit `be_after` (≥60 new rows that arm it), bull_put band
(PROVISIONAL). They are live pre-registered commitments and were the easiest
thing in the old doc to lose. **Silence is not "not met" — check the numbers.**

No rule changed. No config changed. This is a documentation move.

---

## 2026-08-12 — v4 bridge: RECORDED DEVIATION from the pre-registration (written BEFORE the run)

Amends the [pre-registration below](09-v3-closeout.md#2026-08-11--v4-emission-composition-bridge-pre-registration--pre-registrationsf1_selectionv4_bridgemd).
**Nothing has been run.** Written now, while no v4 result exists, because a
deviation decided after seeing numbers is not a deviation, it is a choice.

**What changes: the ~20 re-runs are dropped.** The pre-registration called for
running the v4 prompt over ~20 dates already covered by v3, writing to a scratch
tab. Those are ~20 headless analysis calls, and analysis is the expensive step in
this system. They are also avoidable.

Measured state of the v4 tabs today: **`AnalysisClaude` = 10 rows on one date
(2026-08-11); `AnalysisGPT` = 0.** v4 accrues ~10 rows/day from the normal daily
cadence at no marginal cost, so **~20 dates arrives in roughly four weeks of
changing nothing.**

Checked first, for the record: nothing cached would let a v4 row be reconstructed
for an old date. The pipeline persists the deterministic rollup
(`audit/<date>-rollup.csv`) but sends LLM output straight to Sheets, so a v4 row
on a v3 date genuinely costs a fresh run. There is no copy-paste shortcut.

**What this costs, stated in advance.** Accumulated v4 dates will not overlap v3
dates, so the five tests lose their **date pairing**. Substitute: match on
**`mech_cell`**, a `ROW_COLUMNS` field backfilled across both eras, which encodes
the tape conditions date-pairing was buying.

**Pre-committed caveat, stronger than the original's.** mech_cell matching is
coarser than date matching — it controls for regime, not for the specific day's
flow. Combined with the original's own admission that ~20 dates is thin for a
five-way composition test, this is powered to catch a shift the size of the
v2→v3 credit jump (19% → 34%) and **nothing subtler**. A null result here means
"no large shift detected", never "the populations are the same". Do not let a
null be quoted later as validation.

**Unchanged, and not renegotiable after the numbers land:** the five tests
(structure mix, credit share, plays/day, bear share, ladder tier mix) and the
decision rule — within noise → the v3-derived ladder carries forward; any of the
five shifts → the ladder is UNVALIDATED on v4, keep deploying under v3 rules and
flag every v4 row here.

**Escape hatch, bounded.** If four weeks of tape produces no BEAR or H/E-VOL
date, re-run **≤5** v3-covered dates chosen to fill that specific empty cell —
targeted, and only on evidence the cell is missing. Running `--engine codex`
daily would also double the accrual rate but samples a different engine
population; noted, not recommended.

Interim posture is already what the pre-registration says: deploy under v3 rules.
This is now stated on the operator card itself rather than only here.

**The study is written and gated: `scripts/backtest_study/v4_bridge.py`.** Written
today, while v4 had 10 rows on one date — so nothing in it can have been tuned to
a result. It refuses to produce numbers until the gate is met:

- `MIN_V4_DATES = 20` → exits **rc=2** with the shortfall and the interim posture.
- **Era guard** → exits **rc=3** if the two exports are not v3-then-v4. Era is
  detected from the *schema* (`score_flow`/`score_dealer` present = v3), never
  the filename, because the in-place `vN_` rename leaves both eras exporting as
  "AnalysisClaude" and they are trivially swapped. Run today it correctly aborts
  with *"refusing to compare a book against itself and call the null a
  validation"*.
- v3 is **reweighted to v4's mech_cell mix** (direct standardisation), so a
  difference in regime composition cannot masquerade as a difference in
  behaviour — the specific hazard the date-pairing deviation introduces.

`tests/test_v4_bridge.py` (16 tests) proves the machinery before it ever runs on
real data: both gates fire, `MIN_V4_DATES`/`ALPHA` are pinned at their
pre-registered values, **a v2→v3-sized credit jump (20% → 35%) is detected**, and
standardisation collapses a deliberately confounded 90%-LVOL-vs-50/50 pair to
identical shares while the raw shares differ by >10pts. A study that cannot see
the shift it was built for is not worth waiting a month for.

One divergence from `book.ladder_tier()`, documented in the module: |delta| and
DTE are not columns on an analysis row, so the Tier-B bull_put geometry clause
cannot be evaluated and every bull_put falls to C. That biases the tier mix
**identically in both eras**, which is all a composition comparison needs — but
these tier shares must never be quoted as deployment shares.

---

## 2026-08-12 — live loop promoted to tracked code, and its fill mapper put under test

The close-out entry left this open as a known gap: **`backtests/live_loop/` is
UNTRACKED.** `.gitignore` excludes `backtests/*` and its own comment calls that
tree disposable scratch that "gets deleted periodically" — yet
`stage1_map_fills.py` was 33KB of real code and, with backtest tuning closed, the
**only source of new evidence in the system.** Exactly the mistake the 08-11
refactor fixed for study code by moving it to `scripts/backtest_study/`.

Moved to **`scripts/live_loop/stage1_map_fills.py`**; runs as
`python3 -m scripts.live_loop.stage1_map_fills`. `ROOT = parents[2]` still
resolves to the repo root at the new depth (the stale-ROOT bug that broke 7
studies in the 08-11 move does not recur here — checked, not assumed). Data stays
under `backtests/live_loop/`, which is the correct split: tracked code, disposable
data. Output reproduces exactly — **EXACT 0 / STRUCTURE 2 / SUBSTITUTED 1 /
NONE 15**.

**`tests/test_live_loop.py` — 38 tests**, with the IBKR snapshot copied to
`tests/fixtures/` so it survives a `backtests/` wipe. The 08-11 mis-labelling bug
(`long_call` and `bull_call_spread` both mapping to `debit`, so naked fills were
tallied as STRUCTURE matches) was found **by reading, not by a test**, and its
failure mode is silent — a mislabelled fill does not raise, it quietly corrupts
the evidence base. Now pinned: the `DIRECTION` gate, the
`EXACT ≺ STRUCTURE ≺ SUBSTITUTED` ranking (both row orders), and the ladder port.

**Writing the tests surfaced a seam worth recording.** `classify_structure()`
emits `"single long call"` (spaces) for naked legs but `"bull_call_spread"`
(underscores) for verticals, and `_live_to_canonical()` matches on the spaced
form. Any label that canonicalises to `"unknown"` matches no play and drops to
**NONE — indistinguishable from "no play that day"**, which is precisely the
silent-drop failure the 07-27 entry described and the 08-11 entry corrected for a
different branch. The vocabulary is now pinned by a parametrised test rather than
trusted, including that genuinely unpinnable round-trip closes stay `"unknown"`
instead of guessing.

Still open from the close-out list: `scripts/chart_backtest.py:55-76` re-derives
exit config and knows about neither `regime_exit` nor `structure_exit`.

---

## 2026-08-12 — v1 → v2 → v3 prompt-version comparison, and June-2026 live-vs-analysis audit

Run at operator request. Two questions: (1) did the prompt improve across
versions, (2) how did the June-2026 live book line up with what the analysis
actually emitted. Inputs are the CSV exports in `backtests/to_evaluate/`.
**Real + `strike_expiry_tweak` tiers only** — `bs_options_hist`,
`underlying_trend` and `unevaluable` excluded throughout, per the shipped
`proxy.bs_fallback` off decision.

### 0. Two data traps found on the way in — both would have flipped the answer

**`realized_pnl_pct` changes dtype across versions.** v1 stores it as a
percent STRING (`"1.64%"`, `"-100.00%"`); v2/v3 store decimal fractions
(`0.9994`). A naive `to_numeric` silently drops 153 of 255 v1 rows and leaves
a survivor subset whose median reads +0.60 — i.e. it manufactures a large fake
v1 edge. Any future cross-version pull MUST strip `%` and divide by 100 for v1.
This is the pre-`feedback_percentages_decimal` era leaking into the exports.

**v1 has no BacktestProxy export**, so v1 = 255 real rows with zero tweak tier,
while v2/v3 carry 53/411 tweak rows. Every table below is therefore reported
BOTH as real+tweak and real-only.

### 1. Version comparison — no improvement is measurable

Only **22 signal dates are common to all three** versions (2024-06-17 ..
2025-12-10). v1 covers 56 dates, v2 22, v3 118 (to 2026-04-07), so the
full-window numbers compare different market windows and are not a version
read. On the common window, real+tweak:

    ver    n    win    med E    mean E    total $    PF    med MFE   med MAE
    v1   101   0.554   +0.164   +0.091      8194    1.20    0.70     -0.99
    v2   168   0.488   -0.137   +0.054     14654    1.22    0.91     -0.97
    v3   162   0.481   -0.215   -0.043      4534    1.07    0.82     -0.99

Real-only is worse for v3 (n=101, win 0.455, mean E −0.107, total −$1,100, PF 0.97).

Date-clustered bootstrap on paired per-date mean E, 22 dates, real+tweak:

    v3 - v1   -0.183  [-0.367, +0.002]   n.s.
    v3 - v2   -0.154  [-0.305, -0.008]   SIG (does not survive real-only)
    v2 - v1   -0.029  [-0.268, +0.213]   n.s.

**Verdict: there is no evidence that v2 improved on v1 or that v3 improved on
either.** The single significant result points the wrong way and is
tier-fragile. Emission volume is flat across versions (10.9 / 10.9 / 11.5
analysis rows per common date), so v3 is not buying breadth either.

### 2. Why the comparison cannot be attributed to the prompt anyway

`created_datetime` shows the three books were priced by three different
backtest engines:

    v1 rows created 2026-06-21..06-25    entry_source real+barchart
    v2 rows created 2026-07-06..07-07    entry_source barchart_open+barchart_open
    v3 rows created 2026-07-09..08-10    entry_source barchart_open+barchart_open

The next-day-OPEN entry re-baseline (2026-07-06) lands exactly between v1 and
v2; the DEBIT trailing-stop removal (07-04) and credit `stop_loss` removal
(07-13) also fall inside this span — v1 has 0 `trailing_stop` exits, v3 has 31.
**Engine version is perfectly confounded with prompt version in these exports.**
Exit capture moves the same way (share of MFE>+25% rows that still close red:
v1 0.21, v2 0.37, v3 0.35), which is an exit-rule signature, not a selection one.

Nothing here should be read as "the prompt got worse". The correct statement is
that these exports **cannot answer the question**. To answer it, v1 and v2
analysis rows must be re-run through the CURRENT engine.

### 3. What the gap actually decomposes into (composition, not selection)

Common dates, <180 DTE, medians reweighted to v1's structure mix:

    v1   raw -0.074   v1-mix-weighted -0.079    (n=85)
    v2   raw -0.307   v1-mix-weighted -0.193    (n=141)
    v3   raw -0.488   v1-mix-weighted -0.228    (n=129)

Roughly half of v3's raw deficit is structure composition. Per-structure medians
on common dates:

    structure           v1(n)        v2(n)        v3(n)
    bull_call_spread   +0.528(52)   -0.285(74)   +0.383(56)
    bear_put_spread    +0.116(43)   +0.908(60)   -0.648(51)
    bull_put_spread    -0.803(1)    +0.666(20)   +0.668(35)
    bear_call_spread   -1.517(1)    -1.100(10)   -1.099(16)

Two things line up with already-recorded conclusions and one is new:

- **bear_call is toxic in all three versions** (−1.1 to −1.5). Consistent with
  the 2026-07-13 intake veto; the residual rows here are pre-veto.
- **bull_put is the one genuine v2→v3 gain**: emission share 12% → 20% at a
  stable +0.67 median. That is the shipped `deployment-rules.md` constraint
  showing up in composition.
- **bear_put swings +0.91 (v2) → −0.65 (v3)** on overlapping dates. This is a
  third independent sighting of the bear_put problem and it is NOT explained by
  the engine change alone, since bull_call recovers over the same span.

### 4. The whole book's dollars are long-dated, in every version

Common dates, real+tweak, total $ split at 180 DTE:

    ver     <180d      >=180d
    v1      +23       +8,170
    v2   +10,133      +4,522
    v3    -5,998     +10,533

v3's entire positive dollar result comes from DTE≥180 rows, and its <180d book —
the band the deployment ladder actually trades — is **negative**. These are
real-priced rows, not the bs tier, so this is a different observation from the
2026-08-11 "+$49k of DTE≥180 bs rows" contamination note. It sharpens
`project_longdated_blind_spot`: the ladder is ≤60 DTE by accident, and the
money in the backtest is somewhere the ladder does not go.

### 5. June-2026 live book vs the analysis — coverage gap first

**The v3 AnalysisClaude export contains ZERO June-2026 rows** (v3 months present:
Feb 110, Mar 251, Apr 44, Jul 198, Aug 64). June analysis lives in the v1 export
(107 rows, 06-10..06-24) and the v2 export (45 rows, 06-25..06-30), and there is
no coverage at all before 06-10. So June cannot be evaluated against v3, and no
June row carries `score_total` — **the deployment ladder was not applicable to
anything traded in June.**

Backtest coverage also stops at 2026-04-07, so there are no backtest rows for
June either. The audit below is live-trade vs emitted-play only.

IBKR trades carry no strike/expiry/right, so entries were reconstructed by
grouping fills on order timestamp and matching `average_price` against open
positions. 12 option entry events in June:

    date   tkr   live structure                  analysis that day        verdict
    06-05  NVDA  bull call spread Jun'27 LEAP    (none - no coverage)     UNCOVERED
    06-05  QQQ   debit spread                    (none - no coverage)     UNCOVERED
    06-10  MSFT  LONG CALL naked @41.37          bull call spd 410/480    SUBSTITUTED
    06-12  QQQ   debit spread                    bull call spd 725/760    MATCH
    06-15  NVDA  short call (overwrite)          bull call spd 185/210    OVERWRITE
    06-15  TSM   short call (overwrite)          (none that day)          UNCOVERED
    06-16  MU    bull put 920/940 (SOLD vol)     long strangle, VOL       CONTRADICTED
    06-22  INTC  bull put 115/130 (credit)       bull call spd 145/180    SUBSTITUTED
    06-23  AMD   debit spread                    bull call spd 600/720    MATCH
    06-23  SMH   bear put 470/440                bear put spd 600/540     MATCH
    06-30  NVDA  short call (overwrite)          (none that day)          UNCOVERED
    06-30  TSM   bull call spd 450/530 Dec       bull call spd 460/500    MATCH

4 clean matches, 2 substitutions, 1 direct contradiction, 2 overwrites,
4 uncovered (3 by date-gap, 1 by ticker-gap).

**The `SUBSTITUTED` category from `project_live_walkforward_in_progress` is now
observed twice and in two distinct forms**, which matters because they have
opposite sign:

- **06-10 MSFT — naked long leg where a spread was emitted.** Analysis said
  bull call spread 410/480 163DTE; the live trade was the long call alone at
  41.37, closed 06-22 at 29.63 for **−$1,176**. The emitted short 480 leg would
  have financed part of that. Substitution cost money.
- **06-22 INTC — credit structure where a debit was emitted.** Analysis said
  bull call spread 145/180 and explicitly flagged IV ~95% as "very rich",
  choosing a debit "to neutralize" it; the live trade was a bull PUT credit
  spread 115/130 — same direction, opposite vega. INTC then fell. Both reads
  were wrong on direction, but the emitted 145/180 debit spread would have been
  a near-total loss while the credit spread is at **−$793** unrealized.
  Substitution saved money, and did so by taking the side the analysis's own
  IV comment argued for.

**06-16 MU is the one outright contradiction**: the analysis called RANGE + E-VOL
into earnings and emitted a long strangle (buy vol, IV 99-120%); the live trade
sold vol via a 920/940 put credit spread. Worth logging because the analysis
itself hedged — its Alt clause said the two-sided flow "could be dealers/funds
selling earnings vol", which is the side actually traded.

**Attribution caveat — do not compute June-entry P&L from the current book.**
July is a wall of rolls (50 MU fills, 21 TSM fills between 07-01 and 08-11), so
`average_price` on most surviving positions no longer reflects the June entry.
Only two June entries are untouched: INTC 115/130 (avg 9.3576/15.9720 vs fills
9.35/15.98) at −$793, and NVDA Jun17'27 220C (avg 38.5614 vs fill 38.55) at
−$346. SMH, TSM and MU were all re-struck in July and their marks are NOT June
attribution. Likewise the +$4,966 realized inside June is mostly the 06-22 TSM
close (+$6,159) of an APRIL entry — it is not a June-selection result.

### 6. Actions

- **No rule change.** Nothing here clears a promotion bar.
- **Blocked:** the v1/v2/v3 question cannot be answered from these exports.
  Re-running v1+v2 analysis rows through the current engine is the only clean
  path; until then, treat "v3 is better" as unevidenced in either direction.
- **New watch:** v3 <180d real+tweak book is negative on common dates while
  >=180d carries all the dollars. Check this again on the full v3 window.
- **bear_put:** third sighting, now cross-version. Strengthens the standing
  DEMOTE candidate.
- **Live process:** June ran on v1/v2 prompts with no `score_total`, so the
  ladder was untested in live use. The first genuine live-vs-tier eval needs a
  month where the traded book and a scored analysis tab overlap — July is the
  first candidate (198 v3 rows).

---

## 2026-08-12 (same day, second run) — Stage 1 live-vs-tier eval on July

Follow-up to the section above: July was the first month where the traded book
overlaps a scored v3 analysis tab, so the live-vs-tier eval was finally runnable.
Re-ran `scripts/live_loop/stage1_map_fills.py` on a fresh **2026-08-12** IBKR
snapshot (206 trades vs the old snapshot's 53; 19 open option positions vs 17).

### 0. Four code fixes the wider snapshot forced

The module had only ever seen a 53-trade window. Widening it broke it:

1. **Crash on a non-business-day fill.** `np.busday_offset(fill, -1)` raises on a
   weekend date; IBKR stamped two rows 2026-08-08 (Saturday). Now
   `roll="forward"`, so a Saturday fill resolves to the prior Friday.
2. **Zero-price settlement rows became phantom entries.** A `price == 0` /
   `realized_pnl == 0` row is expiry/assignment bookkeeping, not a fill. They are
   now dropped before entry reconstruction and reported in the header. Zero-price
   rows WITH realized_pnl stay in the closing ledger — those are real expiry P&L.
3. **NONE reasons were collapsed into one misleading label.** Every unmapped
   entry rendered as "no same-ticker play", which reads as "the analysis never
   covered this". False for 21 of them — see §2. Now split four ways.
4. **Snapshot path was hardcoded**; now defaults to the newest
   `ibkr_snapshot_*.json`, with `--snapshot` to re-run an older one, and the
   report name carries the snapshot date so re-runs never clobber.

Two assertions in the generated caveats were also stale and are now computed
rather than asserted.

### 1. The July result — selection compliance

Pooling the mapped entries from BOTH snapshots (see §2 for why pooling is
mandatory) gives **8 mapped live entries**, 2026-07-14 → 2026-08-10:

    signal date  tkr   live structure       confidence    tier   top avail
    2026-07-14   TSM   bull_put_spread      STRUCTURE     VETO   C
    2026-07-16   META  single short put     SUBSTITUTED   VETO   A
    2026-07-17   QQQ   bear_put_spread      STRUCTURE     C      C
    2026-07-28   SMH   bear_put_spread      STRUCTURE     C      A
    2026-07-30   HYG   single long put      SUBSTITUTED   C      C
    2026-08-04   IWM   bear_put_spread      EXACT         C      B
    2026-08-05   TSM   bull_call_spread     STRUCTURE     B      B
    2026-08-07   GLD   bull_call_spread     STRUCTURE     B      B

**4 of 8 were in the top available tier. 2 landed in a VETO cell. Zero Tier-A
plays were ever deployed** — including 07-16 and 07-28, where an A was on the
board and a VETO / C was taken instead.

Both VETO hits are the same cell: **a credit play in RANGE + L-VOL**. That is one
rule, violated twice, and it is the single highest-value thing to fix in live
process. Note 07-16 META is also a SUBSTITUTED row — a naked short put where a
bull_put_spread 620/580 was emitted — so it violates the veto by a route the
analysis never proposed.

### 2. Methodological finding — mapping decays, snapshots are not supersets

Contract identity is inferred by joining a fill price to an open-position
`average_price`; the trades payload has no strike/expiry/right. **Once a
round-trip closes, its identity is unrecoverable.** So the 2026-07-22 snapshot
maps the 07-15 TSM bull_put and 07-20 QQQ bear_put that the 2026-08-12 snapshot
reads as UNKNOWN — those positions have since closed.

**A later snapshot is not a superset of an earlier one.** On the 08-12 snapshot,
21 of 59 unmapped entries fall on dates that DID carry a same-ticker play but
whose live structure could no longer be resolved. Snapshots must be taken on a
regular cadence and their mapped sets pooled. Both facts are now written into
the module's caveats so the next run cannot forget them.

This also relocates the Stage-2 bottleneck. Closed round-trips are no longer
scarce (54, vs the ~30–50 threshold) — **mappability** is the constraint: only 8
entries map at all, across two snapshots.

### 3. P&L, with the attribution caveat that matters

The June audit could not attribute P&L because July rolls had moved every
`average_price` off its entry fill. For the mapped entries this problem solves
itself: **the price-join only matches when `average_price` ≈ the entry fill, so
mapped-and-open entries are by construction un-rolled.** All six open mapped
entries check out (largest gap $0.011/share). Unrealized, as of 2026-08-12:

    tier B     n=2    -$65     (GLD +82, TSM -146)
    tier C     n=3   -$733     (IWM -28, HYG -29, SMH -676)
    tier VETO  n=1   +$726     (META)
    ALL        n=6    -$72

**This does not validate or refute the ladder** and must not be quoted as
evidence: n=6, all unrealized marks on open positions, no exits taken, and the
single VETO row is the best performer. It is recorded so the next snapshot has a
baseline to move against. The ordering is currently the reverse of what the
ladder predicts, on a sample far too small to mean anything.

### 4. Actions

- **No rule change.** n=8 mapped entries decides nothing.
- **Live process, actionable now:** the RANGE + L-VOL credit veto was breached
  twice, and Tier A was passed over twice when available. Both are checkable off
  the analysis row on a deploy morning at zero cost.
- **Snapshot cadence:** take an IBKR snapshot at least fortnightly, keep every
  one, pool the mapped sets. Mappings are lost permanently otherwise.
- **Next gate:** Stage 2 needs mapped entries, not fills. At the current rate
  (~8 per 4 weeks of overlap) a 30-entry mapped book is roughly 3–4 months out —
  unless snapshot cadence rises, which directly raises the mapping yield.

---

## 2026-08-12 — Deployment reference stats added to the operator card (descriptive, no rule change)

**Request:** put win rate / profit factor / MFE / MAE and the regime × structure
breakdown somewhere referable on a deploy morning.

**What was done:** `bear_giveback` ARM S extended and its output written up as
**§7 of `docs/deployment-rules.md`**. ARM S previously printed n / win / PF /
meanR / $; it now also carries `MFE`, `MAE`, and two derived ratios per cell:

    gb  (give-back) = |mean MAE| / mean MFE   — path asymmetry
    cap (capture)   = mean R / mean MFE       — how much of the shown profit
                                                the exit actually banked

These exist because of the standing rule that a results cell is never read on
realized P&L alone: `cap` low with `MFE` high is an EXIT problem, low `MFE` is a
SELECTION problem, and the two demand different fixes. Three new cuts were added
alongside: whole-book debit/credit split, model regime × vol pooled across
structures (so the §1 veto cells can be read directly), and the §3 `bull_put_spread`
geometry gate in-band vs out.

Population: pooled real+tweak, **795 rows**, bs excluded. In-sample throughout.

**Nothing was tuned and no rule changed.** These are summaries of the book the
rules were already fitted on. Four things worth recording anyway:

1. **The ladder is monotone on every new column, not just $.** A/B/C/VETO run
   PF 2.29 / 1.78 / 0.79 / 0.34 and `gb` 0.38 / 0.77 / 1.22 / 2.28. The
   path-asymmetry ordering was never checked before and it agrees. VETO rows go
   2.3× deeper under water than they ever show green.

2. **`bear_put_spread` in mech BEAR_HE is the largest single loss cell in the
   book** — n=218, −$40.3k — with `MFE +0.67` but `cap −0.25`. It confirms from a
   third direction that bear is an exit problem, not a selection one (the 08-11
   bear-arm conclusion). §5 rows 2–3 are what manage it.

3. **`win` and `PF` disagree routinely and the card now says so.**
   `bull_put_spread` is 68% win / PF 0.94; `bull_call_spread` is 60% win / PF 2.05.
   Anyone reading win rate alone would rank those backwards.

4. **Two override temptations are now documented in place, with the reason not
   to take them.** BULL + C-VOL `bull_call_spread` (PF 5.01, n=40) outperforms
   most of Tier A but stays B — A-vs-B was validated at tier level, not cell by
   cell. BEAR + H-VOL `bull_call_spread` (n=9) looks positive but the pooled
   regime cell is −$20.6k at a 30% win rate, which is what §1.2 vetoes.

**Caveats written into §7.8:** in-sample; small-n cells are directional at best;
`$` is size-weighted so it can disagree with `meanR`; v3-derived, not re-confirmed
on v4; bs rows excluded.

**Regenerate with** `python -m scripts.backtest_study run bear_giveback --arms S`
— the command is in an HTML comment at the top of §7 so the snapshot can be
refreshed without hunting for it.
