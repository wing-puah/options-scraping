# Rollback-trigger power census + first evaluation — pre-registration

**Registered 2026-08-24, before any run on the 2026-08-24 17:09 export refresh.**
Modules: additive census blocks in `exit_switch_mech_study` (STEP 3(f)),
`bear_arm` (be_after census), `exit_mechanism_study --side credit`
(Attempt-13 comparator census), all built on `scripts/backtest_study/lib/triggers.py`.

## What this registers

The four shipped-rule forward triggers have existed only as prose — nothing in
the repo computed "affected dates", so they have never been evaluated
(`deployment-evidence.md` §"Open pre-registered rollback triggers": *"Never
read silence as 'not met' — check the numbers"*). This registration adds the
census and commits to how the FIRST evaluation is read. The trigger texts
below are quoted verbatim from their original registrations and are the
immutable commitment; this file only pins what those texts left unspecified.

## The four triggers (verbatim)

1. **BEAR_HE trail** (config/backtest.yml `regime_exit` comment, shipped
   2026-07-22): "ROLLBACK TRIGGER (pre-registered, evaluate at ≥25 affected
   BEAR+H/E dates of NEW data): revert to PROD if the BEAR_HE cell's total
   gain vs PROD is ≤ 0, OR if the affected-date median gain is < 0. Passing
   instead promotes it from exception to gated-and-cleared."
2. **LVOL tef-null** (same comment block): "NOT shipped — still gated" behind
   the corrected gate (research log 2026-07-22 addendum c): "median>0 among
   AFFECTED dates, ≥25 affected, total>0, both halves+, no perturbation flip
   → then ship trail .50/.50 in mech BEAR+H/E + tef-null in mech L-VOL."
3. **Bear-debit `be_after: 0.50`** (config/backtest.yml `structure_exit`
   comment, shipped 2026-08-11): "ROLLBACK TRIGGER (pre-registered, evaluate
   at >=60 NEW bear-debit rows that actually arm the ratchet, i.e. reach peak
   P&L >= +0.50): revert `enabled` to false if the total gain vs PROD on
   those rows is <= 0, OR if the mean R delta on the affected rows is < 0,
   OR if any single year of the pooled book flips negative."
4. **Credit sl-none** (Attempt 13, research log 2026-07-13): "Rollback
   trigger: sl-none loses to sl-1× on the next ≥15-row fresh bull_put
   window."

## Pinned specifications (what the texts left unspecified)

- **Population**: the era-resolved current exports, real + strike_expiry_tweak
  proxy rows, `include_bs=False` everywhere (the 2026-08-11 standing hazard).
- **"Affected"** (one definition, `lib/triggers.py::is_affected`): a row is
  affected by a rule iff base and variant configs produce different outcome
  triples `(exit_reason, days_held, round(pnl_pct, 4))` under the frozen
  harness replay — the same triple the calibration gate compares. An affected
  DATE is a signal date with ≥1 affected row.
- **"Arming"** (trigger 3): peak of the stored mark path
  `round(pnl_of(mark), 10) ≥ +0.50`, the trigger's literal wording.
- **"Fresh window"** (trigger 4): bull_put rows signal-dated AFTER 2026-07-13
  (the Attempt-13 ship date). Floor 15 rows.
- **Census-first rule**: every run prints the census (n affected rows, n
  affected dates, the floor, MET / UNDERPOWERED). A trigger whose floor is
  not met gets NO reading — the census itself is the recorded result.
- **Estimators where a floor is met**: trigger 1/2 — per-affected-date summed
  pnl_pct delta (variant − PROD), median and total over affected dates;
  trigger 3 — total $ gain vs PROD on arming rows, mean-R delta on affected
  rows, per-year mean-R delta sign on the pooled bear-debit book; trigger 4 —
  $ and mean-R comparison sl-none vs sl-1× on the fresh window.

## Decisions taken before reading any number (operator, 2026-08-24)

- **Trigger 3 status: CORRELATED-WINDOW RE-READ.** The v4 book's arming rows
  are new plays from a new prompt version, but they sit on the SAME historical
  signal dates (2024-01→2025-08) as the v3 book the rule was fitted on. The
  evaluation runs now (the ≥60 floor is met on the fresh export), but it is
  recorded as a within-window replication, NOT out-of-sample confirmation.
  Action follows only if the evidence is decisive: a revert condition firing
  here (a shipped rule failing even in-window) counts and is acted on after
  surfacing to the operator; a PASS promotes nothing — it is logged as
  "held on correlated re-read", and promotion to cleared still waits for
  genuinely new dates.
- **Trigger 4 scope: CENSUS + COMPARATOR ONLY.** The v4 credit book (73 rows,
  70 bull_put — first book to calibrate exactly against shipped CREDIT_PROD)
  is 58/70 2024-dated, not the fresh window §2.7 parked the credit-knob
  thread on. The `sl 1x (pre-Attempt-13)` grid line and the census are
  printed; NO tuning read is taken and the thread stays parked.

## Ship criteria

None. This registration ships no rule. Its outcomes are: (a) a recorded
census per trigger, (b) for trigger 3 only, a revert/hold decision under the
correlated-re-read reading above, surfaced to the operator before any config
change. All other trigger evaluations wait for their floors on new data.
