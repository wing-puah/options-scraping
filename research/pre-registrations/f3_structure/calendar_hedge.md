## 2026-08-13 — `calendar_hedge`: PRE-REGISTRATION (written BEFORE the study was built or run)

**Question.** The 2026-08-12 `vol_sleeve` run left one CANDIDATE: the calendar
is uncorrelated with the deployed book (+0.088, CI spans zero) and returns
+0.336 CI [+0.124, +0.486] on its worst decile — a per-structure subgroup of a
POOLED gate, n=13 rows over 7 dates. This study re-derives that number under a
pre-registered pick rule, a fixed universe, and a strict fill definition. It
will be a different number on a smaller n; that is the point. A bounded sweep
of untried wrappers runs SEPARATELY behind it (ARM S below).

**Frozen inputs.** `book.load_book(include_bs=False)`; deployed book =
`top_k_per_day(ladder_rank, k=3, A|B)`; synthesis/pricing =
`vol_sleeve.build_legs` + `_strike_index` and `bear_rewrap.{entry_date_for,
net_entry, net_marks, leg_details, size_contracts, reconstructs}` UNCHANGED;
exits = frozen `harness.replay` under `DEBIT_PROD`. Nothing in `harness.py`,
`vol_sleeve.py`, `bear_rewrap.py`, `config/backtest.yml`, or
`docs/deployment-rules.md` is edited.

**Universe.** Only dates where the ladder actually deployed, and a candidate
must be **fillable on the ladder's own entry session** — both legs cached on
`grid[0]`, NOT the loose ≤5-day entry-lag rule `vol_sleeve` used (you cannot
decide to hedge Monday and be filled Friday). The lag distribution under the
loose rule prints as a sensitivity. Excluded and counted: `entry_net ≤ 0`
(crossed/stale market — vol_sleeve saw 2/183) and `far_exp ≤ near_exp`.

**Pick rules (decision-time only; the list is CLOSED here).**
P1 nearest-ATM (min |K*−S|/S among the day's fillable calendars); P2 longest
near-leg DTE; P3 shortest near-leg DTE; P4 widest expiry gap; P5 same ticker as
the day's top-ranked deployed position (P1 tie-break); P6 ETF underlyings only,
then P1. **THE RULE IS P1** — geometry not score, the closest analogue of the
shipped bear-hedge convention, and implicitly what produced the vol_sleeve
number. P2–P6 print as a robustness fan; a P2–P6 pass with P1 failing is a
candidate for a future window, never a ship.

**Sizing.** One hedge per day, ≤½ position: `bear_rewrap.size_contracts` × 0.5
on the shipped $50k basis (directly comparable with the shipped bear sleeve).
Portfolio effect at sleeve fractions f ∈ {0, 0.25, 0.50, 1.0}, exactly as
`bear_deploy` D3.

**Gates that must pass before any hedge number is read.**
- **H0 FILL:** P1 produces a fillable hedge on ≥60% of deployed-book dates AND
  ≥60% of the deployed book's worst-decile dates (both print side by side; the
  gate fails on either). Unfillable days are carried as f=0 in every portfolio
  line, never dropped from the denominator. A hedge unavailable exactly when
  needed is not a hedge.
- **H0b FRESHNESS:** the headline must survive `stale_at_cap ≤ 3` and
  `pct_real ≥ 0.5` (`vol_sleeve.mark_quality`).

**Exit.** `DEBIT_PROD` (pt .90 / sl .75 / tef .75) — the profile the candidate
was measured under; no calendar-specific exit (that would stack a second free
parameter on the pick rule). The frozen harness already handles calendars: the
grid ends at the SHORT leg's expiry, `_price_asof` never carries a leg past its
own expiration, and multi-expiry net marks are deliberately unclamped. As a
LABELLED SENSITIVITY only: the same table under hold-to-near-expiry
(pt/sl/tef all None) — it may not change the verdict; it exists so the
write-up can say whether the verdict is exit-shape-dependent.

**Criteria (H1–H5, mirroring bear_deploy D1–D5, renamed to avoid confusion).**
- H1 STANDALONE (context, NOT a gate): mean E and R of the P1 sleeve,
  date-clustered CI, per-year signs. Negative standalone does not fail a hedge.
- **H2 HEDGE CONTRIBUTION (the primary gate, D2's rule verbatim):** on
  deployed-book dates, (a) date-level correlation of the two daily series < 0;
  (b) mean sleeve R on the deployed book's worst-decile dates > 0 with
  date-clustered CI excluding zero; (c) worst-quartile tail positive in ≥2
  evaluable years. All three.
- H3 SIZING (D3 verbatim): the largest f whose max drawdown AND worst single
  date are both no worse than f=0.
- H4 CONDITIONAL PICK: within-date paired comparison of P1 vs the day's average
  fillable calendar and vs each of P2–P6.
- H5 TIMING (POST-HOC, labelled): gates on `mech_cell == BEAR_HE`, H-VOL,
  RANGE+C/L-VOL, and earnings-inside-DTE (vol_sleeve's one CI-clearing
  conditional: +0.356 vs −0.035, CI [+0.111, +0.664], n=42). Candidate-only.
- **POWER STOP:** if the P1 worst-decile cell has fewer than 10 positions,
  H2(b)'s CI is NOT read and H2 is recorded **NOT EVALUABLE** — not "failed".
  Expected: the cell will be ≈7–9 under a 1/day rule; NOT EVALUABLE is a
  likely and correct outcome, and the honest conclusion is "needs new dates".

**Baselines (two — a change from vol_sleeve, which compared vs no hedge
only).** (i) the deployed ladder alone at $50k; (ii) the ladder PLUS the
SHIPPED bear hedge sleeve (`|delta|` descending, ½ size, 1/day). The calendar
must beat the hedge the operator already has, not just the empty seat.

**Reconstruction gates.** R1 book calibration quoted. R2
`bear_rewrap.reconstructs` on every source row feeding the universe. R3 the
deployed-book replay reproduces the deployed line the 08-12 `vol_sleeve` report
printed on the same exports (220 positions / 90 dates / $63,553). **R4
(the critical one):** with the pick rule disabled and the LOOSE fill rule, this
study must reproduce vol_sleeve's calendar cell EXACTLY — 183 rows, meanR
+0.158, $28,059, exit mix time_exit 124 / pt 28 / dollar_stop 22 / cap_open 5
/ sl 4 — otherwise the gap between +0.336 and whatever H2 prints cannot be
attributed (pick rule vs re-implementation drift). Non-zero exit on failure.

**ARM S — the structure sweep. Runs only AFTER the H arm has printed, only
under `--arm S`, in a separate invocation and report file.**
- S1 `put_calendar` (short near put + long next-cached-expiry put at K*;
  plan-time cache feasibility 577/786 groups). S2 `put_diagonal` (short near
  put at K*, long next-expiry put at nearest cached strike BELOW; 561/786).
  S3 `narrower` (bear vertical, short pulled UP to the highest cached strike
  below the long — mirror of `sub_wider`). S4 `wider` and S5 `long_put` rerun
  UNCHANGED from `bear_rewrap` as internal plumbing controls with known
  answers (wider −0.056; long_put +0.002 failing 2026). S6 `iron_condor`
  (bull-put + bear-call wings at nearest cached-or-scraped strikes around K*,
  same expiry) — included ONLY if the leg scrape reaches ≥60% four-leg group
  coverage (plan-time cache-only feasibility is 214/786, far short); otherwise
  NOT EVALUABLE with the coverage number printed.
- Missing legs are scraped FIRST by `scripts/collector/fetch_sweep_legs.py`
  (resumable: one cache file per contract, `--limit` chunks, skip-existing,
  manifest CSV) into the same cache under the same naming; synthesis results
  are checkpointed to `backtests/sweep_cache/synth_results.csv` so an
  interrupted run resumes instead of restarting.
- MULTIPLICITY: a sweep cell is a CANDIDATE only if its worst-decile CI
  excludes zero at Bonferroni α = 0.05 / (n_structures × n_pick_rules), is
  right-signed every year present, and clears H0. **Nothing in ARM S can ship
  from this run**; the maximum verdict is carry-to-next-window.
- OUT OF SCOPE, so it is not re-litigated: ratio spreads (frozen harness
  `_defined_risk_bounds` is None for unbounded net quantities — a harness
  constraint); straddle/strangle (CLOSED 2026-08-12).

**Ship ceiling.** Nothing changes `config/backtest.yml`. The maximum outcome is
an optional second hedge sleeve added to `docs/deployment-rules.md` §4,
requiring H0 MET ∧ H0b not flipping the verdict ∧ H2 MET ∧ H3 deployable at
f ≥ 0.25. Anything less is a candidate.
