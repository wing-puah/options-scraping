# Pre-registrations

One file per study, containing that study's pre-registration verbatim: the
question, frozen inputs, criteria, and gates written down **before** the study
was built or run. These are immutable planning artifacts — a pre-registration
is never edited after the fact. If the plan changes, that is a NEW dated
section appended to the same file, so the change stays visible rather than
overwriting the original commitment.

They deliberately do NOT live in [`../current.md`](../current.md), which is a
rolling narrative log that gets pruned into `../archive/` over time. Pruning a
pre-registration would destroy its evidentiary value, so each one gets its own
file here instead.

`python -m scripts.study_review <study>` reads the matching file and hands it
to the two independent analyst agents (`research-analyst` × 2 +
`research-validator`), who grade the study's run against what was committed to
here — see [`../replication-protocol.md`](../replication-protocol.md).

## Files

| File | Study |
|---|---|
| [`account_sim.md`](account_sim.md) | `account_sim` |
| [`macro_event_study.md`](macro_event_study.md) | `macro_event_study` |
| [`calendar_hedge.md`](calendar_hedge.md) | `calendar_hedge` |
| [`vol_sleeve.md`](vol_sleeve.md) | `vol_sleeve` |
| [`volume_signal.md`](volume_signal.md) | `volume_signal` |
| [`v4_bridge.md`](v4_bridge.md) | `v4_bridge` (module: `scripts/backtest_study/f1_selection/v4_bridge.py`) |
| [`selection_order.md`](selection_order.md) | `selection_order` (module: `scripts/backtest_study/f4_deployment/selection_order.py`) |
| [`financed_spread.md`](financed_spread.md) | `financed_spread` |
| [`staged_exit.md`](staged_exit.md) | `staged_exit` |
| [`portfolio_delta.md`](portfolio_delta.md) | `portfolio_delta` |
| [`emission_timing.md`](emission_timing.md) | `emission_timing` |
| [`concurrency_correlation.md`](concurrency_correlation.md) | `concurrency_correlation` — **registered 2026-08-22, module NOT yet written.** The plan exists before the code on purpose; see the file's own "dead ends" table for the v3 cuts it must not re-find. |
