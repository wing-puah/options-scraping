# volume_signal — brief

> This is a plain-language brief, not the registration. The binding text is [the registration](../../pre-registrations/f2_management/volume_signal.md); where the two differ, the registration wins.
> Latest outcome: PRIMARY v3 `NULL` (2026-08-15). On v4, `NULL` (2026-09-28), after earlier v4 runs had printed `PATH-VOL-PROXY` · [record](../../study-results/f2_management/volume_signal.md).
> Nothing else here is a result.

## The question

Underlying share volume is the one column on disk that no study had read. Does it condition anything the book cares about?

The primary hypothesis is about exits and paths, not selection. Bear debits were diagnosed as an exit problem, and the sub-arming give-back census is a path effect. Reading the column also meets the ML-search reopen condition, which allows new columns only.

Every closed-thread rule applies. Any selection read must be within structure from the first look.

## What it compares

The study builds three features from data already on disk. It reads them on the pooled `real` and `strike_expiry_tweak` book. Labels below are `volume_signal H1`, `H2` and `H3`.

| Object | What it does | Kind |
|---|---|---|
| `volume_signal H1` | Tests whether high unusual-O/S rows give back more, within structure. Compares the HIGH `os_ratio` tercile with the LOW tercile on exit capture and on the share of rows that peak below the `be_after` arming threshold and finish ≤ 0 | PRIMARY, path and exit |
| `volume_signal H1` mechanism test | One variant only: `be_after: 0.50` on non-bear debit rows in the HIGH tercile, against [PROD](../../glossary.md#prod), leave-one-date-out | PRIMARY, path and exit |
| `volume_signal H2` | Descriptive tercile cut of `rvolz20` within structure. No direction is committed and no adoption path exists | exploratory |
| `volume_signal H3` | Re-cuts any H1 separation within `amihud20` terciles | control |
| Selection | Mean R and total dollars by feature tercile, within structure only | SECONDARY |

The three features:

- `os_ratio` = `Contracts × 100 / Volume(signal date)`. Only the tercile order is read.
- `rvolz20` = z-score of `ln(Volume)` on the signal date against the trailing 20 sessions ending the prior session.
- `amihud20` = mean over 20 sessions of `|session log return| / (close × Volume)`.

Bear debit rows are excluded from the H1 variant arm. They already carry the shipped breakeven stop. Their give-back census by tercile still prints.

Rescaled tickers keep `os_ratio`. Their `rvolz20` and `amihud20` are withheld, because a split fabricates a volume spike. A window feature needs at least 15 usable positive-volume sessions.

Option volume is the flow-scrape contract count, not total listed volume. No read may treat it as the literature's exact numerator.

## How it is judged

**Measure.** [MFE/MAE](../../glossary.md#mfe) separation, [R](../../glossary.md#r) separation and leave-one-date-out ([LOO](../../glossary.md#loo)) fold summaries.

**Population.** The pooled `real` and `strike_expiry_tweak` book through `load_book`. The exit variant runs on calibrated debit rows only. Descriptive tables may use the full book with credit rows flagged. The v3 and v4 eras are never pooled.

**Gates.** A failed gate gives a non-zero exit.

- `G1` calibration: `replay(DEBIT_PROD)` reproduces the stored exit reason, days held and rounded R on every calibrated debit row. The build ruling adds the row's cost back and cuts the path at `path_data_end`; the bar is unchanged.
- `G2` coverage: volume-feature hit rates, source split, O/S join hit rate and withheld counts print before any conditional number.
- `G3`: `MIN_CELL_N = 20`. Thinner cells print n and are not read.
- `G4`: no annualised return, Sharpe or time-to-recover.
- `G5` out-of-fold discipline: descriptive tercile tables are in-sample and labelled so. Only LOO fold summaries and walk-forward test rows can support adoption.

**Selection read.** A within-structure separation must survive `protocol.walk_forward_splits`, with tercile boundaries fitted on train dates only, before it may be called a candidate.

**Bar for the candidate verdict.** All three must hold.

1. H1's LOO median and total are both positive.
2. The sign holds on the log's standard both-window cut.
3. H3 does not collapse the separation.

## Possible verdicts

| Token | What it means |
|---|---|
| `VOLUME-CONDITIONS-EXITS` | A candidate, not a ship. It queues an independent-window confirmation |
| `LIQUIDITY-PROXY` | `amihud20` absorbs the separation, so H3 fires |
| `PATH-VOL-PROXY` | Path width moves together with no R separation: `mfe_sep × (−mae_sep) > 0`. Higher peaks with shallower drawdowns do not count |
| `NULL` | None of the above survives its gate. The volume column is closed and the live pipeline never pays the version bump |

## What could ship

Nothing ships under any outcome. A surviving result queues an independent-window confirmation. Only that could justify feeding volume to the live pipeline. That change is an input change, so it needs a version bump and new tabs.

## What this study cannot tell you

- Whether volume helps selection on its own. Selection is a secondary read within structure.
- Anything about `rvolz20`. It has no committed direction and no adoption path.
- Anything about total listed option volume. The numerator is the flow-scrape count.
- Anything about bear debits as a group. They are excluded from the variant arm.
- The exit-variant set can never grow. It is exactly `{be_after: 0.50}`.
