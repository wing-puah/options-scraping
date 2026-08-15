# Study results — the per-era record

One file per study. One append-only section per **(export era, git sha)**, each
quoting verbatim what that study's report actually printed.

```
research/study-results/
├── f1_selection/     bear_arm.md  bear_position_study.md  mech_regime_recut.md  …
├── f2_management/    bear_giveback.md  exit_mechanism_study.md  next_day_move.md  …
├── f3_structure/     bear_rewrap.md  calendar_hedge.md  vol_sleeve.md
└── f4_deployment/    account_sim.md  account_sim-compounding.md  bear_deploy.md  …
```

```bash
source .venv/bin/activate
python3 -m scripts.study_results                 # record every study with a report
python3 -m scripts.study_results --study bear_arm
python3 -m scripts.study_results --dry-run       # show what it would append
python3 -m scripts.study_results --include-refusals   # record "too thin" runs too
make study-record                                # same thing
```

## Why this folder exists

`backtests/study_output/*-latest.txt` looks like an archive and is not one. It is
**gitignored scratch**, and on 2026-08-15 that cost real evidence twice in a day:

1. A re-export of the bare `backtests/to_evaluate/analysis - *.csv` files
   silently changed which population fourteen studies were computing on. The
   reports kept their filenames and their confident verdict banners; only the
   numbers underneath had moved from v3 to v4.
2. A `run --all` then overwrote roughly fifteen of those reports. `backtests/`
   has no git history, so the originals were simply gone. Commit `53b7167`
   folded what could still be read into `research/` verbatim and cut the
   directory to three files.

The structural fix shipped alongside: `scripts/backtest_study/lib/era.py` made
the export era explicit and checked, every provenance header now names the era it
read, and the policy is that **a study runs on the current era only**.

That policy is precisely what makes this folder necessary. A study may only print
the current era's answer, so the moment v4 matures and the suite is re-run against
it, v3's reports are overwritten by v4's — and the v3-vs-v4 comparison the whole
era mechanism exists to enable would have nothing left on the v3 side. The record
has to be taken while the era is still current, and it has to live somewhere
tracked. This is that somewhere.

## The folders mirror `scripts/backtest_study/`

A study's record sits under the same family folder its module does:

    scripts/backtest_study/f1_selection/bear_arm.py
    research/study-results/f1_selection/bear_arm.md

`f1` → `f2` → `f3` → `f4` is not alphabetical filing — it is **the order a play
moves through the system: pick it, manage it, wrap it, fund it.** That is why the
folders carry the numeric prefix, it is the taxonomy `catalog.py::FAMILIES`
renders onto the study map, and it means the records read in the same sequence
the pipeline does: selection evidence before management evidence before structure
before sizing.

The mirror is *derived*, never listed. `scripts/study_results.py::family_of()`
reads the family off the study module's own parent directory via the runner's
`study_paths()` — so moving a study between families moves its record with it,
and no table here can fall out of step. The record's **filename** never changes
when that happens: the folder is navigation, the stem is identity, and the stem
is what `research/current.md` cites and what the `(era, sha)` history hangs off.

Arm stems (`account_sim-compounding`) are not modules, so they file under their
parent study's family — `f4_deployment`, beside `account_sim.md`.

## The rules

- **Append-only.** Sections are never rewritten, re-ordered, or deleted — not by
  `scripts/study_results.py`, and not by hand. A record that turned out to be
  wrong gets a *later* section saying so; it does not get edited away.
- **Keyed on (era, sha, input fingerprint).** Three facts, because a number
  means nothing without all three:

  | field | says | changes when |
  |---|---|---|
  | `era` | which **population** was read | a prompt-version bump |
  | `sha` | which **code** produced it | any commit |
  | `inputs` | **how much** of that population there was | the era accrues dates |

  Re-running with all three unchanged appends nothing and says so. Any one of
  them moving **is** a new result and gets its own section.

  The third field is not decoration. An era is not a fixed dataset — it accrues
  dates while the code stands still. v4 refuses at the 30-date floor with 10
  dates today and will cross that floor purely from the backfill queues running,
  with no commit in between. Keyed on `(era, sha)` alone, the refusal would have
  claimed `(v4, shaA)` and the first real v4 result — the entire point, the v4
  side of the comparison — would have been dropped as "already recorded". The
  fingerprint digests the input **row counts** the provenance header already
  lists (not their mtimes: a re-export of unchanged data moves every mtime while
  the book is identical, and recording that as a fresh result is pure noise).

  **Back-compat clause:** a marker carrying no `inputs=` field predates the
  fingerprint — the nineteen era-v3 sections written on 2026-08-15 — and matches
  any fingerprint for its `(era, sha)`. Those sections are the only surviving
  copy of the v3 reports, so failing to recognise them and appending a duplicate
  beside each is the one behaviour that is not acceptable. Markers written from
  now on always carry the field, so the clause is inert going forward. The marker
  is parsed as an open bag of `field=value` pairs for the same reason: the key
  has already had to grow once, and the next growth must cost a back-compat
  clause rather than a migration.

- **Refusals are skipped by default.** A designed refusal (`REFUSED — era v4 has
  10 dates; this study needs 30`) is the study's correct current **status**, not
  a **result**. Twenty near-identical "too thin" sections would bury the findings
  this folder exists to keep, and they carry nothing a glance at the era does not
  already tell you. Pass `--include-refusals` for the audit trail of when a gate
  was still closed. This is a signal-to-noise choice and *not* a safety one —
  only true because of the fingerprint above: the real result that arrives once
  the era thickens keys differently from the refusal, so it records either way.
  The skip is scoped to **declared** refusals; an undeclared non-zero exit is a
  real break and is always recorded.
- **Verbatim, never paraphrased.** The quoted block is byte-identical to what
  `scripts/study_map/summary.py::summarize()` extracted from the report — the
  study's own VERDICT/CONCLUSION banner where it printed one. Every section
  states its `excerpt` kind so a reader can tell a verdict from a designed
  refusal from an unlabelled tail:

  | kind | means |
  |---|---|
  | `verdict` | a banner section the study titled VERDICT / CONCLUSION / DECISION / … |
  | `refusal` | a non-zero exit the study **declared** as designed — a pre-registered gate not met, or a guard refusing to compare a book against itself. Correct behaviour. |
  | `failure` | a non-zero exit that was *not* declared — a real break |
  | `matched` | lines stating a pre-registered criterion (MET / NOT MET / …) |
  | `tail` | no marker found — literally the last lines of the report |

- **Nothing is added.** No statistic the study did not print, no gloss, no grade.
  If the report said nothing quotable, the section says that instead.

## How this relates to `research/current.md`

They are different jobs and neither replaces the other.

| | `research/current.md` (+ `archive/`) | `research/study-results/` |
|---|---|---|
| holds | the **reasoning** — what a result meant, what shipped because of it, the deep verbatim folds of the tables that mattered | the **index** — what each study last printed, per era |
| written by | a human (or Claude) after reading a report | `python3 -m scripts.study_results`, mechanically |
| shaped by | the argument being made | one section per (era, sha), always the same fields |
| answers | "why do we deploy this way?" | "what did `bear_arm` say on v3, and does v4 still say it?" |

Write-ups still go to `current.md` — that is unchanged. This folder is what makes
a *cross-era* write-up possible at all, by keeping the earlier era's answer alive
after its report has been overwritten.

## Related

- `scripts/study_results.py` — the recorder (its docstring carries the same history)
- `scripts/backtest_study/lib/era.py` — how an era is detected and enforced
- `scripts/study_map/catalog.py` — the hand-written standing verdict per study
- `research/study-map.md` / `site/study-map.html` — what each study is *for*
