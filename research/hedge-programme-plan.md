# The hedge programme, code consolidation plan

**Three criteria are written six, four and three times, and none of the copies
is tested against the others.** This is the plan to reduce them to one each, to
merge two studies that ask the same question at two scopes, and to retire one
study into the one that already rebuilds its cell. It was written as a plan and
executed the same day. [Status](#status) says what landed.

_Written 2026-09-07 against the spine, [`hedge-programme.md`](hedge-programme.md).
Read that first. It says which question each study answers and what each one last
printed._

<a id="status"></a>
## Status

**Executed 2026-09-07. Every study reconciled byte-identical and nothing
shipped.** Seven commits, one study at a time, in this order.

| Commit | What it did |
|---|---|
| `a9b713a` | `lib/hedge_criteria.py` created; `bear_deploy` reads it |
| `8c03502` | `hedge_timing` reads it |
| `5be4ba6` | `vol_sleeve` deleted; `lib/sleeve_synth.py` created |
| `4ed865f` | `calendar_hedge` reads it |
| `7187ca2` | `hedge_concentration` merged into `hedge_exposure --admitted` and deleted |
| `3d20781` | `bear_rewrap` reads the daily series |
| `0d27a37` | `financed_spread` reads the daily series |

**Retired means deleted, by operator decision on 2026-09-07.** The plan below
proposed keeping `vol_sleeve.py` on disk with the catalog's `retired` field set.
That is not what was done. Both `vol_sleeve` and `hedge_concentration` were
DELETED as modules, and neither the `retired` field nor
`tests/test_study_map.py:107` was touched. The two verdicts survive as the
**DELETED** rows in [`study-map.md`](study-map.md), beside their frozen
[`study-results/`](study-results/) prints and their immutable
pre-registrations. Nothing that either study printed is lost: `vol_sleeve`'s
synthesis layer is `lib/sleeve_synth.py`, which `calendar_hedge` `R4` runs, and
`hedge_concentration`'s whole report prints from the `--admitted` arm.

**The option-history cache was repaired first.** `calendar_hedge` `R2` failed on
three reconstruction keys, not the two named in
[`next-steps.md`](next-steps.md) §0. Six files were restored from the
`research-caches-20260905-1111.tar.gz` Drive snapshot:

| File | Key it unblocks |
|---|---|
| `IWM_20260529_245.00P` | the two named in §0 |
| `MSTR_20250627_420.00C` | the two named in §0 |
| `SPY_20250725_555.00P` | 2025-06-05 SPY |
| `KWEB_20250425_32.00P` | 2025-03-06 KWEB |
| `KWEB_20250425_35.00P` | 2025-03-06 KWEB |
| `TSLA_20250228_360.00P` | 2025-01-07 TSLA |

`R2` now reads `reconstructs: 1180 / 1180 (100.0%)` and `R2 PASS` on the
installed export.

**What remains.** The two sleeve-sizing implementations outside the fraction
sweep, at `f4_deployment/account_sim.py:988` and
`f4_deployment/portfolio_delta.py:363`, are untouched and still out of scope.
[Deliverable 3](#held), the far-call fetch note, is still held. `bear_rewrap`
`ARM P` keeps its own worst-decile cutoff and its own `P1`/`P2` verdicts on
purpose; the reason is in [`current.md`](current.md).

The work is grouped by the question it serves. The shared criteria library is
common to all four questions, so it comes first.

<a id="shared"></a>
## The shared criteria library

New module, `scripts/backtest_study/lib/hedge_criteria.py`. It holds one hedge
contribution rule, one sizing rule, and the one drawdown function they both read.

### What exists today

The hedge contribution rule, `D2` in its origin, appears in six modules.

| File and line | Symbol | How it differs from the origin |
|---|---|---|
| `f4_deployment/bear_deploy.py:209`, `:221` | `daily_series`, `d2_hedge` | the origin, correlation plus tail plus per-year sign |
| `f4_deployment/hedge_timing.py:622` | `daily_dollars` | dollar leg only, no tail cut at all |
| `f3_structure/vol_sleeve.py:413`, `:549` | `daily`, `q2` | own bootstrap CI, tail ordered by dollars, no year clause |
| `f3_structure/bear_rewrap.py:559` | `report_portfolio` | decile as a value cutoff, tail verdict is CI based |
| `f3_structure/calendar_hedge.py:932` | `h2_contribution` | adds a floor of 10, carries unfillable dates at zero |
| `f3_structure/financed_spread.py:1481`, `:1492`, `:1651` | `sleeve_daily`, `cell_corr`, `report_descriptive` | correlation is the criterion, the tail is labelled not a criterion |

The sizing rule, `D3` in its origin, appears four times in the fraction-sweep
shape.

| File and line | Symbol | How it differs from the origin |
|---|---|---|
| `f4_deployment/bear_deploy.py:306`, `:328`, `:348`, `:367` | `_sleeve_dollars`, `_sweep`, `_verdict`, `d3_sizing` | the origin, fractions 0, 0.25, 0.5, 1.0 |
| `f4_deployment/hedge_timing.py:635`, `:652`, `:671`, `:677` | `sleeve_pick`, `policy_daily`, `_policy_stats`, `h4_portfolio` | two fractions, gated policy, fails closed on an empty cut |
| `f3_structure/calendar_hedge.py:1053`, `:1077`, `:1112` | `bear_sleeve_dollars`, `_sweep`, `h3_sizing` | two baselines, drops the downside-deviation column |
| `f3_structure/vol_sleeve.py:604` to `:611` | inline block | no baseline row, no verdict, normalised to one average position |

Two further sleeve-sizing implementations sit outside the sweep shape, at
`f4_deployment/account_sim.py:988` to `:1007` and
`f4_deployment/portfolio_delta.py:363` to `:389`. They pick one position a day
by descending delta, which `calendar_hedge.py:1053` implements a third time.
They are named here and are out of scope for the first pass.

The drawdown function exists as three bodies.

| File and line | Status |
|---|---|
| `lib/mtm_curve.py:471` | the canonical body, re-exported from `f4_deployment/bear_deploy.py:60` |
| `f3_structure/vol_sleeve.py:428` | a port, untested, will not follow a change to the canonical one |
| `f4_deployment/hedge_timing.py:605` | a documented verbatim fork, untested |

### The reference, and how a copy is deleted

**`bear_deploy` is the reference for `D2` and `D3`, because it is the origin the
copies name.** `hedge_timing`, `vol_sleeve` and `calendar_hedge` name the module
itself. `bear_rewrap.py:560` names the criterion `D2` without naming the module.
`financed_spread` names neither. It attributes its join to
[`bear_rewrap` `ARM P`](arm-index.md#bear_rewrap) / `P2` instead, one hop further
out. That does not unseat the reference, but the claim is three modules and not
five.

`lib/mtm_curve.py:471` is the reference for the drawdown function, because
`tests/test_mtm_curve.py:246` already pins that `bear_deploy` re-exports it
rather than owning a second body.

A copy is not deleted because it looks the same. Each one is reconciled first
against that study's last recorded report, one study at a time, in
[`study-results/`](study-results/). The reconciliation is a run of the study on
the era its record names, with the copy replaced by the library call, and a
comparison of every printed figure against the recorded section. Only an
identical print permits the deletion.

**A mismatch is a finding, not a merge conflict.** It is written up in
[`current.md`](current.md) with the two figures and the population, and the
deletion stops there. Two of the copies are load-bearing in this exact way.
`hedge_timing.py:605` says in its own docstring that it was copied rather than
imported so that `bear_deploy`'s recorded numbers can never move because that
file changed. `calendar_hedge.py:936` says its rule is the origin's verbatim.
Both are commitments about numbers, so the merge has to preserve numerical
identity and not merely intent.

### The fixture test

The library is pinned the way `lib/harness.py` is pinned, by
`tests/test_harness_replay.py` against a committed CSV fixture. That test builds
each case from the fixture row alone, never from the shipped profile constants,
then asserts an exact equality on the recorded outcome with no tolerance.

`tests/fixtures/hedge_criteria.csv` follows the same pattern. One row per case,
each carrying a `case_id`, a `why` column stating what the row is there for, the
input series inline, and the expected verdict and figures. The fixture guards
itself the way the harness fixture does, with tests asserting that every branch
is reached: a tail that clears and one that does not, a correlation of each sign,
a year clause that fails on one year, an empty cut that must fail closed, a
fraction sweep whose winner is not the largest fraction, a drawdown series that
only rises, and a cell below the power floor. Case ids are unique and no row
carries a broker or account field. The fixture is hand-curated from cases the
recorded reports already contain, and it is generated by no script, because a
generator is how an expected value gets quietly rewritten to whatever the code
now prints.

<a id="q1-work"></a>
## Q1, when to hedge

`hedge_timing` stays a separate module. It carries its own immutable
pre-registration and it answers a question no other study asks. Its share of the
consolidation is two items only.

- **`max_drawdown` at `hedge_timing.py:605` is replaced by the library import.**
  The bodies are byte-identical today, so the reconciliation is a re-run and a
  diff of the recorded verdict block against the record.
- **`daily_dollars` at `:622` is replaced by the library's daily series.**
  It is the dollar leg of the origin's helper with the return leg removed.

No arm label and no gate label changes. The report must keep printing
`ARM H1`, `ARM H2`, `ARM H3` and `ARM H4` under those labels, per trigger family.

<a id="q2-work"></a>
## Q2, what to hedge with

**`vol_sleeve` is retired into `calendar_hedge`.** `calendar_hedge` already
rebuilds `vol_sleeve`'s calendar cell in-process and compares it row for row,
under its own gate `R4`, and imports the synthesis layer rather than copying it.
The straddle and the strangle are the only part of `vol_sleeve` that
`calendar_hedge` does not already carry, and both were answered.

**Retired means the module is deleted** (operator, 2026-09-07). `vol_sleeve.py`
is gone and its catalog entry with it, because `tests/test_study_map.py:73`
asserts the catalog's keys equal the runner's directory glob: a deleted file
with a surviving entry fails, and a surviving file with no entry fails too. The
`retired=` field is therefore still unused, and
`tests/test_study_map.py:107` is untouched. The verdict survives as the
**DELETED** row in [`study-map.md`](study-map.md#structure), which that test
also checks.

**Every `VS.` reference in `calendar_hedge.py` resolves to `lib/` rather than to
the deleted module.** The import at `calendar_hedge.py:100` reached twelve
symbols, not three. They moved to `lib/sleeve_synth.py`, unchanged, and
`calendar_hedge` imports them from there, so nothing imports a study that is not
there. `lib/sleeve_synth.py` is a deliberate exception to the `lib/` layering
rule: it imports pricing helpers from `f3_structure/bear_rewrap`, on the
precedent of `lib/live_select.py`, because `R4` compares row for row and a third
copy of the entry rule is the failure `R4` exists to catch. Its docstring says
so. Nothing moved into `calendar_hedge` itself, because `R4` exists precisely to
catch a second copy of the entry rule drifting, and a copy inside the study is
exactly the copy `R4` is there to refuse. These are the symbols that moved.

| Group | Symbols |
|---|---|
| the builder and its strike lookup | `build_legs`, `_strike_index`, `paired_strikes` |
| the trade synthesizer | `synthesize`, `synth_trade` |
| the statistics helpers | `daily`, `path_stats`, `pearson`, `corr_ci`, `boot_ci_diff_by_date` |
| the marks and the formatter | `mark_quality`, `_f` |

`synthesize` is the one that matters most. Gate `R4` runs it as the second side
of its row-for-row comparison, so a retirement that left it behind would have
left `R4` importing a module that is not there.

`bear_deploy` and `calendar_hedge` stay separate modules. They ask different
questions and each has its own immutable pre-registration.

<a id="q3-work"></a>
## Q3, how much to hedge

The sizing rule moves into the library with `bear_deploy` as the reference. The
three consumers keep their own registered shapes on top of it.

| Consumer | What stays local to it |
|---|---|
| `bear_deploy` `D3` | the four-fraction grid and the downside-deviation column |
| `hedge_timing` `ARM H4` | the two-fraction grid, the gated policy, the closed-fail on an empty cut |
| `calendar_hedge` `H3` | the second baseline, the deployed ladder plus the shipped bear sleeve |

The library exposes the criterion, meaning the largest fraction whose drawdown
and worst date are both no worse than carrying nothing. It does not own the grid.
A study that narrows its grid is making a registered choice, so the grid stays in
the study.

<a id="q4-work"></a>
## Q4, portfolio make-up

**`hedge_exposure` and `hedge_concentration` merge into one module with an
admission arm.** They are the same question at two scopes. `hedge_concentration`
already imports 32 symbols from `hedge_exposure`, including its whole pricing and
evaluation stack, its printers and its constants. The only thing it redefines is
the handful of functions that read the admitted book rather than the whole book.

The merged module takes an arm selecting the population: the whole book, which is
`hedge_exposure` today, or the admitted book that `account_sim` actually takes,
which is `hedge_concentration` today. Each arm writes its own report stem, the
way `account_sim`'s arms do.

**Every registered gate and arm keeps printing under its registered label.** Both
registrations are immutable in substance, and six labels collide between them.

| Label | `hedge_exposure` means | `hedge_concentration` means |
|---|---|---|
| `ARM C` | concentration-gated proxy put on the whole book | the same, Stage 2 only, on the admitted book |
| `ARM M` | measurement, two curves on the unhedged book | the same on the admitted book |
| `ARM N` | random-admission null, 200 seeds | the same, matched on episodes |
| `ARM R` | delta-equivalent short, feasibility floor | the same on the admitted book |
| `G-POWER` | 25 trigger dates per cell | 25 trigger dates per cell, Stage 2 |
| `G-MTM` | curve reconciliation, exit code 4 | the same code, imported not restated |

The merged module prints each label prefixed by its arm, so a reader can tell
which population a line came from, and neither registration's vocabulary is
renamed. `hedge_concentration`'s Stage 1 and Stage 2 verdict grammars stay
separate from `hedge_exposure`'s six study-level words, because a merged verdict
would be a new claim.

The two libraries these studies share, `lib/concentration.py` and
`lib/hedge_instrument.py`, have exactly these two importers, and
`lib/forward_drawdown.py` has one. They stay in `lib/` and are unaffected.

<a id="bookkeeping"></a>
## What each retirement and merge changes outside the code

### The catalog

`scripts/study_map/catalog.py:72` defines `Study`. Its `retired: str | None`
field at `:77` is documented as being about whether a study can be run at all,
rather than about what it argued. A retired study carries a one-line reason and
date. `run --all` then skips it.

**No study is retired, and the field is still unused.** `grep "retired="` in
that file returns nothing, and `tests/test_study_map.py:107` asserts
`catalog.retired_studies() == {}`. The two studies retired before were deleted
outright on 2026-09-05, with their verdicts moved to
[`study-map.md`](study-map.md#structure). This pass did the same thing, so the
field went unused again.

There is no `superseded` field. The word appears only inside verdict prose.

| Study | Catalog action taken |
|---|---|
| `vol_sleeve` | entry removed, because the module is gone and the runner discovers studies from the directory. Its verdict is now the **DELETED** row in [`study-map.md`](study-map.md#structure) |
| `hedge_concentration` | entry removed, for the same reason. Its verdict is the **DELETED** row in [`study-map.md`](study-map.md#deployment) |
| `hedge_exposure` | entry kept, verdict prose extended to name both arms |
| `lib/hedge_criteria.py`, `lib/sleeve_synth.py` | added to the INFRA table, which `tests/test_study_map.py:115` checks against `run.INFRA`'s `lib/*.py` glob |

### The frozen records

[`study-results/`](study-results/) is append-only and machine-written by
`scripts/study_results.py`. Sections are never edited and the tool has no note
flag. So a superseded note is added the only way the format allows, as a later
section.

**The retiring study's final run prints the supersession line in its own report,
and `make study-record` appends that report as a new section.** Nothing is
hand-edited, and the earlier sections stay exactly as they are.

That route has a precondition the plan cannot assume. `summarize()` records
`excerpt verdict` only for a report carrying a VERDICT, CONCLUSION or DECISION
banner, and `vol_sleeve.py` prints none — every section of its record reads
`excerpt tail`, which `extract()` produces after the banner search fails. So
taking this route means adding a banner to the retiring study, which is a code
change to `vol_sleeve.py` and has to be named as one. The line must then sit
inside the banner's first 12 non-blank lines and stay under 150 characters
(`scripts/study_map/summary.py:66`), or it is clipped or dropped without an
error.

The fallback is cheaper and carries no code change. If a study is removed before
such a run, or no banner is added, its record simply ends, and the supersession
is stated in [`current.md`](current.md) and in the catalog's `retired` string
instead.

### The label index

[`arm-index.md`](arm-index.md) is checked by `tests/test_arm_index.py`. That test
scans every study module and every pre-registration for `ARM <X>` tokens and
requires each to appear in the index. It does not see gate labels of the `G-`
form, nor the `H0` to `H5` criteria, nor the `D1` to `D5` criteria. Those are
hand-maintained.

| Change | What the index needs |
|---|---|
| the merge | the merged module's section carries both studies' `ARM` labels, each qualified by its arm |
| `vol_sleeve` retired | it has no index section today, so nothing is removed. Its `Q1` to `Q3` gates were never indexed |
| the new library | no `ARM` token, so no index entry |

### The tests

| Test | Why it fires |
|---|---|
| `tests/test_study_map.py:73` | the catalog must cover exactly the runner's study list, so removing a module fails until the catalog matches |
| `tests/test_study_map.py:91` | [`study-map.md`](study-map.md) must name every study in the catalog |
| `tests/test_study_map.py:107` | it asserts nothing is retired, so retiring `vol_sleeve` requires editing this test deliberately |
| `tests/test_study_map.py:115` | the catalog's infrastructure table must match the runner's, and `run.INFRA` globs `lib/*.py`, so ANY new module under `scripts/backtest_study/lib/` fails until it is listed — `hedge_criteria.py` and everything Q2 relocates there |
| `tests/test_arm_index.py:103` | any renamed or new `ARM` token fails until the index carries it |
| `tests/test_calendar_hedge_r4.py` | it imports `vol_sleeve` directly, so the retirement moves what it imports |
| `tests/test_studies_hedge_concentration.py` | it imports `hedge_exposure` and asserts the shared exit code, so the merge rewrites its imports |
| `tests/test_mtm_curve.py:246` | it pins the single drawdown implementation and should gain the two removed forks |

The registry itself needs no edit. `scripts/backtest_study/run.py:232` discovers
studies by globbing the family folders and keying on the bare file stem, so
adding or removing a module is a file operation. `scripts/backtest_study/__init__.py`
registers nothing and is documentation only.

Two package docstrings are already stale and should be corrected in the same
pass. `f4_deployment/__init__.py` omits five of its eight modules, including three
hedge studies, and `f3_structure/__init__.py` omits `financed_spread`. Nothing
tests them, which is why they drifted.

<a id="sequencing"></a>
## Sequencing

**Nothing in this plan starts while either of two things is true.**

- **The queue D campaign is running.** `scripts/analyze_bt_queue.sh` is untracked
  and in flight. A study run during it reads a moving export.
- **The two robustness worktrees are unmerged.** Two of their items change every
  number a re-run would print, the missing cost model and profit booked before
  the fill. They merge only after the campaign ends, and the suite is re-run once
  after that ([review](robustness-review.md),
  [`next-steps.md`](next-steps.md) §0 and §2.11).

Three further constraints hold throughout.

- **No export is installed as a side effect.** Reconciliation runs read the era
  its record names. `scripts/export_tabs.py` is not part of this work.
- **`lib/harness.py` is untouched.** Every recorded conclusion rests on it, and
  its own docstring says a genuine change is a new study that copies it.
- **One study at a time.** A copy is reconciled, then deleted, then the next.
  A single commit removing six copies cannot say which one moved a figure.

<a id="held"></a>
## Held until this plan is reviewed

Deliverable 3, the far-call fetch pre-run note for
[Q2](hedge-programme.md#q2-what-to-hedge-with), is written only after this spine
and plan are reviewed. It will cover a far-call fetch mode for the hedge arm,
covering every deployed date and every ticker the book entered that day, taking
the at-the-money strike at the next listed later expiry, read either from the
flow CSV or from that ticker's other cached contracts. Its point is that the
registered rule already asks for the long leg at the first later listed expiry at
the same strike, and the cache does not hold it, which is why the sleeve fills on
about a third of the worst-decile dates. The fetch completes the data the
registered rule reads. It does not change the rule, it does not choose a strike
the chain may not list, and it is a separate collector from
`fetch_sweep_legs.py`, which serves the structure sweep and was last run
2026-08-13.
