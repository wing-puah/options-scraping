"""Per-(study, era) durable record — what each study printed, kept where git can see it.

    python3 -m scripts.study_results               # record every study with a report
    python3 -m scripts.study_results --study bear_arm
    python3 -m scripts.study_results --dry-run     # print what it would append

--- Why this exists ----------------------------------------------------------
`backtests/study_output/*-latest.txt` is GITIGNORED SCRATCH. It reads like an
archive — one stable filename per study, a provenance header, a verdict banner —
but nothing about it is durable, and on 2026-08-15 that bit twice in one day:

  1. A re-export of the bare `backtests/to_evaluate/analysis - *.csv` files
     silently changed which population fourteen studies were computing on. The
     reports kept their filenames and their confident banners; only the numbers
     underneath had moved to a different era.
  2. A `run --all` then overwrote roughly fifteen of those reports. There was no
     copy anywhere. `backtests/` has no git history, so the originals were gone.

Commit `53b7167` salvaged what could still be read, folded it into `research/`
verbatim, and cut the directory down to three files. The structural fix landed
alongside it: `scripts/backtest_study/lib/era.py` made the export era EXPLICIT
and CHECKED, every report's provenance header now names the era it read, and the
standing policy is that a study runs on the CURRENT era only.

That policy is what makes this module necessary. A study is only ever allowed to
print the current era's answer, so the moment v4 matures and the suite is re-run
against it, v3's reports are overwritten by v4's — and the v3-vs-v4 comparison
that the whole era mechanism exists to enable would have nothing on the v3 side
to compare against. The record has to be taken while the era is still current,
and it has to live somewhere tracked. `research/study-results/` is that
somewhere: one file per study, one APPEND-ONLY section per (era, git sha).

The folder tree MIRRORS `scripts/backtest_study/` — a study's record sits under
the same family folder its module does:

    scripts/backtest_study/f1_selection/bear_arm.py
    research/study-results/f1_selection/bear_arm.md

`f1` -> `f4` is the order a play moves through the system (pick it, manage it,
wrap it, fund it), which is why the folders carry the numeric prefix at all, and
the mirror is derived from the module's ACTUAL parent directory rather than from
any table here — see `family_of()`.

--- What it does NOT do -----------------------------------------------------
It does not parse a report. `scripts/study_map/summary.py::summarize()` already
does that — header fields, input row counts and mtimes, exit code, and the
study's own VERDICT/CONCLUSION banner tagged with how it was found. This module
calls it and formats the result. That is deliberate: this repo has already paid
for three independent provenance parsers drifting apart, and a fourth one whose
whole job is to be quotable would be the worst place yet to reintroduce the bug.

It does not summarise, re-word, grade, or editorialise. CLAUDE.md's research-tier
rule — "Last-run excerpts are quoted verbatim, never paraphrased" — applies here
more sharply than anywhere else, because a record is read years later by someone
who no longer has the report. So the excerpt is written byte-identical to what
`summarize()` returned, inside a fence, carrying its `excerpt_kind` so a reader
can tell a verdict from a designed refusal from an unlabelled tail. No statistic
the study did not print is ever added to a section.

--- Why the key is (era, git sha, input fingerprint) -------------------------
The era says what POPULATION produced the number. The sha says what CODE did.
Both are part of what the number MEANS — the same reasoning the provenance
header itself encodes — so a re-run of the same era under different code is a
genuinely new result and gets its own section, appended below the old one rather
than replacing it.

The third field is there because the first two are not enough, and finding that
out cost a near-miss. An era is not a fixed dataset: it ACCRUES dates while the
code stands still. v4 today has ten dates and every study refuses at the
thirty-date floor; v4 will cross that floor purely from the backfill queues
running, with no commit in between. Keyed on (era, sha) alone, the refusal would
have claimed `(v4, shaA)` and the first REAL v4 result — the entire point of the
exercise, the v4 side of the v3-vs-v4 comparison — would have been silently
dropped as "already recorded". `fingerprint()` closes that: it digests the input
ROW COUNTS the header already lists, so a bigger book records separately.

Nothing here ever rewrites or deletes a section; a re-run whose era, code and
book are all unchanged appends nothing at all and says so.

--- Refusals are skipped by default -----------------------------------------
A designed refusal (`REFUSED — era v4 has 10 dates; this study needs 30`) is the
study's correct current STATUS, not a RESULT. Nineteen near-identical "too thin"
sections would bury the findings this folder exists to keep, and they carry no
information a single glance at the era does not — so `record()` skips them
unless asked. `--include-refusals` records them for anyone who wants the audit
trail of when a gate was still closed.

This is a signal-to-noise choice and NOT a safety one, which is only true
because of the fingerprint above: the real result that arrives once the era
thickens keys differently from the refusal, so it records either way, whichever
setting was used the first time round.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from scripts.backtest_study import run as study_runner
from scripts.backtest_study.lib import era as era_mod
from scripts.study_map import catalog, summary
from scripts.study_map.summary import RunSummary

ROOT = Path(__file__).resolve().parents[1]
DEST_DIR = ROOT / "research" / "study-results"
OUT_DIR = summary.OUT_DIR

# Runnable names under `backtest_study/` that write a `-latest.txt` but are not
# studies and have no era-scoped result to preserve. `book` is the runner's
# `--validate` diagnostic — the study map files it under infrastructure for the
# same reason. Keep this in step with `catalog.INFRA` if another one appears.
NON_STUDY_STEMS = frozenset({"book"})

# The key marker is written as an HTML comment so it renders as nothing and can
# never be mistaken for content. Idempotency reads THIS line and never the
# human-facing prose above it: a heading is free to be reworded later without
# silently making every past section unrecognisable and re-appending the lot.
#
# Parsed as an OPEN BAG of `field=value` pairs rather than as a fixed shape,
# because the key has already had to grow once (era+sha -> era+sha+inputs) and
# a positional pattern would have orphaned every section written before the
# growth — re-appending the lot, which for an append-only record is the one
# unrecoverable mistake. A future field costs a back-compat clause, not a
# migration.
_KEY_LINE = re.compile(r"^<!-- key (.*) -->$")
_KEY_FIELD = re.compile(r"(\w+)=(\S+)")

# The three fields of the key, in the order they are written. See `SectionKey`.
KEY_FIELDS = ("era", "sha", "inputs")

# `summarize()` hands back the header's raw era field, which reads
# "v3 (prefixed exports)" — the parenthetical says how the era was resolved, not
# which era it is. Sections are keyed on the token alone so the two spellings of
# one era can never open two records.
_UNKNOWN = "unknown"

# Reports written before the era line existed (pre-2026-08-15) genuinely do not
# record their population. That silence is what let a v4 re-export be read as v3
# across fourteen studies, so it is recorded as unknown and never guessed at.
_ERA_NOTE = ("this report predates the era header — its population is genuinely "
             "unrecorded, not assumed")

# Short labels for the three exports that decide a study's population, so the
# population line reads as a census rather than as four file paths. Derived from
# era.EXPORTS rather than restated, so a tab rename moves both at once.
_EXPORT_LABELS = {tab: key for key, tab in era_mod.EXPORTS.items()}
_ERA_PREFIX = re.compile(r"^v\d+_")

# Where a record goes when its family cannot be resolved — a `-latest.txt` whose
# study module has been deleted or renamed since the run. Filing it beside the
# families rather than guessing one keeps the mirror honest: an unfiled record
# is visibly unfiled, where a wrong folder would just read as a wrong family.
UNFILED = "unfiled"

# How many hex characters of the input digest go in the key. Seven matches the
# git short sha it sits beside — long enough that a collision across the handful
# of runs one study ever accumulates is not a real risk, short enough to read.
FINGERPRINT_LEN = 7

# The excerpt kinds that are a STATUS rather than a RESULT. See
# `record()`'s `include_refusals` and the README: a designed refusal is the
# study correctly declining to answer, and recording twenty near-identical
# "era too thin" sections buries the results the folder exists to keep.
STATUS_ONLY_KINDS = frozenset({"refusal"})


@dataclass(frozen=True)
class SectionKey:
    """What makes one recorded result distinct from another.

    Three facts, because a number means nothing without all three:

      era     which POPULATION was read (v3, v4, …).
      sha     which CODE produced it — the same discipline the provenance
              header encodes by printing the sha at all.
      inputs  a fingerprint of HOW MUCH of that population there was.

    The third one is not redundant, and leaving it out was a real defect. An
    era is not a fixed dataset: it ACCRUES dates while the code stands still.
    v4 refuses at the 30-date floor with 10 dates today and will cross that
    floor purely from the backfill queues running, with no commit in between —
    so `(v4, shaA)` would be "already recorded" from the refusal, and the first
    REAL v4 result, the whole point of the exercise, would be silently dropped.
    """

    era: str
    sha: str
    inputs: str

    def marker(self) -> str:
        return ("<!-- key " + " ".join(f"{f}={getattr(self, f)}" for f in KEY_FIELDS)
                + " -->")

    def matches(self, found: dict[str, str]) -> bool:
        """Whether an already-present marker records THIS result.

        BACK-COMPAT CLAUSE: a marker carrying no `inputs=` field predates the
        fingerprint (the nineteen era-v3 sections written on 2026-08-15) and
        matches any fingerprint for its (era, sha). Those sections are the only
        surviving copy of the v3 reports — the scratch was overwritten hours
        after they were taken — so the one behaviour that is not acceptable
        here is failing to recognise them and appending a duplicate beside
        each. Newly written markers always carry the field, so the clause is
        inert for everything from now on and never widens a real comparison.
        """
        if found.get("era") != self.era or found.get("sha") != self.sha:
            return False
        return "inputs" not in found or found["inputs"] == self.inputs


@dataclass
class Outcome:
    """What `record()` did for one study — the CLI's one line per study."""

    name: str
    # "appended" | "already recorded" | "no report" | "skipped (refusal)"
    action: str
    key: SectionKey | None = None
    excerpt_kind: str = ""
    path: Path | None = None
    section: str = ""    # the text that was (or would have been) appended

    @property
    def detail(self) -> str:
        """The CLI's right-hand column — what identifies this result."""
        if self.key is None:
            return f"no {self.name}-latest.txt on disk"
        return (f"era {self.key.era} · sha {self.key.sha} · "
                f"inputs {self.key.inputs} · {self.excerpt_kind}")


def era_token(run: RunSummary) -> str:
    """The bare era name from the header's era field, or `unknown`."""
    return run.era.split()[0] if run.era.strip() else _UNKNOWN


def fingerprint(run: RunSummary) -> str:
    """A short digest of the run's input ROW COUNTS — "how much book was this?".

    Row counts, deliberately, and not the mtimes that sit beside them in the
    header. The two disagree in both directions and only one direction is
    harmful:

      * A re-export of unchanged data moves every mtime. Keying on mtime would
        record a fresh section for a run that read exactly the same book —
        noise, and worse, noise that makes a genuine change hard to spot.
      * Two different books with identical counts across all four inputs would
        share a fingerprint. That needs a swap that preserves the row count of
        each export independently, which the accrual-only growth pattern of an
        era does not produce.

    So this fingerprints the population's SIZE, which is the thing that moves
    when an era accrues. It is not a content hash and does not pretend to be:
    the exports are not read here, only the header the runner already wrote.

    Labelled and sorted before hashing, so the runner listing its inputs in a
    different order can never look like a different book. MISSING inputs are
    part of the fingerprint too — a run that could not find an export read a
    genuinely different book from one that could.
    """
    parts = sorted(f"{_input_label(path)}={rows}" for rows, _mt, path in run.inputs)
    parts += sorted(f"{_input_label(p)}=MISSING" for p in run.missing_inputs)
    if not parts:
        # Nothing to fingerprint. `none` rather than the hash of an empty
        # string, so a reader can see at a glance that the size is unknown
        # rather than merely opaque.
        return "none"
    digest = hashlib.sha256("\n".join(parts).encode()).hexdigest()
    return digest[:FINGERPRINT_LEN]


def section_key(run: RunSummary) -> SectionKey:
    """The identity of one recorded result. See `SectionKey`."""
    return SectionKey(era=era_token(run), sha=run.git_sha or _UNKNOWN,
                      inputs=fingerprint(run))


def base_study(name: str) -> str:
    """The study module a report stem belongs to — `name` itself, or its parent
    study when `name` is one of the runner's ARM stems.

    An arm files its report under `<study>-<suffix>` (see
    `backtest_study/run.py::arm_plan`), so `account_sim-compounding` belongs to
    `account_sim`. Matched by LONGEST module-name prefix rather than by
    splitting on the first `-`, because study names contain hyphens nowhere but
    could, and because a longest-prefix match degrades to "no parent" instead of
    to a wrong one.

    THE single arm-stem rule in this module. `family_of()` calls it rather than
    re-deriving the parent, so a record and its family folder can never disagree
    about which study an arm belongs to.
    """
    modules = study_runner.study_paths()
    if name in modules:
        return name
    candidates = [m for m in modules if name.startswith(f"{m}-")]
    return max(candidates, key=len) if candidates else name


def family_of(name: str) -> str:
    """The family folder a record mirrors — `f1_selection` … `f4_deployment`.

    Read off the study module's OWN parent directory, via the runner's
    `study_paths()`. Three other spellings of this were available and all three
    are worse:

      * a hardcoded name -> folder table here, which is a copy that drifts the
        first time a study moves between families;
      * `catalog.STUDIES[name].family`, which is the bare word "selection" and
        is a SECOND hand-maintained fact — `tests/test_study_map.py` asserts a
        module's folder equals its catalog family precisely because the two can
        disagree, and keying off the folder means this cannot be the thing that
        makes them;
      * the module's dotted path, which is the same fact spelled less directly.

    The runner already treats the folder as the source of truth for navigation
    (`study_paths()` walks `FAMILY_DIRS`), so this mirror moves with a study the
    moment its file does — the stem, and therefore the record's filename and its
    `(era, sha)` history, stay put. Folder is navigation; stem is identity.
    """
    modules = study_runner.study_paths()
    path = modules.get(base_study(name))
    return path.parent.name if path is not None else UNFILED


def record_path(name: str, dest_dir: Path = DEST_DIR) -> Path:
    """Where `name`'s record lives: `<dest>/<family>/<name>.md`."""
    return dest_dir / family_of(name) / f"{name}.md"


def discover(out_dir: Path = OUT_DIR) -> list[str]:
    """Every name worth recording: the catalog's studies, plus any other report
    stem sitting in `out_dir`.

    The extra stems are the runner's ARMS — `account_sim-compounding` and
    friends — which file their results under their own stem (see
    `backtest_study/run.py::arm_plan`). They are real, separately-parameterised
    results that a future era must be comparable against, and the study map's
    own scope (catalog names only) would drop them on the floor. `base_study()`
    is what puts them under their parent study's family folder.

    One caveat, harmless today and worth stating before it stops being: an arm
    stem is not a module, so `summarize()` resolves its designed-refusal exit
    codes to the shared era codes from `lib/era.py` rather than to its parent
    study's declaration. Every study that declares any today declares exactly
    those two codes, so the two answers coincide. A study that later declares a
    code of its OWN would need `summarize()` reading them through `base_study()`
    too.
    """
    names = set(catalog.STUDIES)
    if out_dir.exists():
        names |= {p.name[: -len("-latest.txt")]
                  for p in out_dir.glob("*-latest.txt")}
    return sorted(names - NON_STUDY_STEMS)


def _input_label(path: str) -> str:
    """`results` / `proxy` / `analysis` for the population exports, else the stem.

    The era prefix is stripped because the section already states the era on its
    own heading; repeating `v3_` four times across one line adds nothing.
    """
    stem = Path(path).stem
    stem = stem.split(" - ")[-1]
    stem = _ERA_PREFIX.sub("", stem)
    return _EXPORT_LABELS.get(stem, stem)


def _population(run: RunSummary) -> str:
    """One line of "how much of what", from the header's own input table."""
    if not run.inputs:
        return "(no inputs recorded)"
    counts = " · ".join(f"{rows} {_input_label(path)}" for rows, _mt, path in run.inputs)
    stamps = sorted({mtime for _rows, mtime, _p in run.inputs})
    if len(stamps) == 1:
        dated = f"(inputs dated {stamps[0]})"
    else:
        # Mixed mtimes are normal — the regime table is refreshed on its own
        # cadence — so show the span rather than picking one and implying the
        # whole population was exported at that moment.
        dated = f"(inputs dated {stamps[0]} … {stamps[-1]})"
    return f"{counts}  {dated}"


def _fence(lines: list[str]) -> str:
    """A fence long enough that nothing in `lines` can close it early.

    A study report is fixed-width plain text and has never contained a backtick
    run, but the excerpt is quoted VERBATIM and must stay that way — clipping or
    escaping a line to make the fence work would be exactly the paraphrase this
    module exists to prevent, so the fence gives way instead.
    """
    longest = 0
    for line in lines:
        m = re.match(r"^\s*(`{3,})", line)
        if m:
            longest = max(longest, len(m.group(1)))
    return "`" * max(3, longest + 1)


def render_section(name: str, run: RunSummary, today: date | None = None) -> str:
    """The markdown for one recorded result. Facts, then a verbatim quote."""
    key = section_key(run)
    stamp = (today or date.today()).isoformat()

    git = run.git or _UNKNOWN
    exit_code = "?" if run.exit_code is None else str(run.exit_code)
    elapsed = run.elapsed or "?"
    kind = run.excerpt_kind or "none"
    # `refused` is the runner's own verdict on the exit code (a pre-registered
    # gate not met, not a crash). Saying so on the run line keeps a correct
    # refusal from reading as a broken study a year from now.
    if run.refused:
        exit_code += " (designed refusal)"

    # The heading carries the WHOLE key, not just the era. Two sections of one
    # era are now routine — an era accrues dates, and the same code re-run on a
    # bigger book is a different result — so a heading naming only the era would
    # make a file of them indistinguishable until you read the marker comment,
    # which renders as nothing.
    lines = [
        f"## era {key.era} · inputs {key.inputs} · sha {key.sha} — recorded {stamp}",
        key.marker(),
        "",
    ]
    if key.era == _UNKNOWN:
        lines += [f"> era {_ERA_NOTE}.", ""]
    lines += [
        f"population  {_population(run)}",
        f"run         {run.run_at or '?'} · git {git} · exit {exit_code} · {elapsed}",
        f"command     {run.command or '?'}",
    ]
    if run.missing_inputs:
        lines.append("missing     " + " · ".join(run.missing_inputs))
    lines += [f"excerpt     {kind}", ""]

    if run.excerpt:
        fence = _fence(run.excerpt)
        lines += [fence, *run.excerpt, fence, ""]
    else:
        lines += ["(the report printed nothing quotable)", ""]
    return "\n".join(lines) + "\n"


def _file_header(name: str) -> str:
    """The one-time preamble of a study's record file.

    The catalog's question is quoted because it is the repo's own standing
    description of what the study asks, and a reader opening this file years
    later needs it. The standing VERDICT is deliberately NOT copied here: it is
    hand-maintained in `catalog.py` and `research/current.md`, and a copy would
    drift out of step with both while looking authoritative.
    """
    study = catalog.STUDIES.get(name)
    lines = [f"# {name} — per-era record", ""]
    if study is not None:
        lines += [f"**Question.** {study.question}", ""]
    lines += [
        "Append-only. One section per (export era, git sha); newest last. The "
        "excerpts are quoted verbatim from the study's own report — see "
        "[README.md](../README.md) for why this folder exists.",
        "",
    ]
    return "\n".join(lines) + "\n"


def existing_markers(path: Path) -> list[dict[str, str]]:
    """Every key marker already in `path`, as its raw `field=value` bag.

    Returned unparsed-into-a-key on purpose: an old marker may carry fewer
    fields than `SectionKey` has today (see `SectionKey.matches`), and forcing
    it into today's shape would have to invent the missing ones.
    """
    if not path.exists():
        return []
    found = []
    for line in path.read_text().splitlines():
        m = _KEY_LINE.match(line.strip())
        if m:
            found.append(dict(_KEY_FIELD.findall(m.group(1))))
    return found


def is_recorded(path: Path, key: SectionKey) -> bool:
    """Whether `path` already holds a section for `key`."""
    return any(key.matches(found) for found in existing_markers(path))


def record(name: str, out_dir: Path = OUT_DIR, dest_dir: Path = DEST_DIR,
           today: date | None = None, dry_run: bool = False,
           include_refusals: bool = False) -> Outcome:
    """Append `name`'s current report as a new section, unless already recorded.

    A designed REFUSAL is skipped unless `include_refusals`. See the module
    docstring for the reasoning; in short, a refusal is the study's correct
    current STATUS and not a RESULT, and this folder is read to answer "what did
    this study find on v3?". With the input fingerprint in the key, skipping is
    a signal-to-noise choice rather than a safety one: the real result that
    arrives once the era thickens keys differently from the refusal and records
    either way.
    """
    run = summary.summarize(name, out_dir)
    if not run.ran:
        # Not an error: a retired study is never run again by design, and a
        # fresh checkout has no reports at all until something is run.
        return Outcome(name=name, action="no report")

    key = section_key(run)
    path = record_path(name, dest_dir)
    section = render_section(name, run, today)
    common = dict(name=name, key=key, excerpt_kind=run.excerpt_kind,
                  path=path, section=section)

    if run.excerpt_kind in STATUS_ONLY_KINDS and not include_refusals:
        # Deliberately checked BEFORE `is_recorded`: a skipped refusal is
        # reported as skipped whether or not one happens to be on file, which
        # is the truthful thing to print.
        return Outcome(action="skipped (refusal)", **common)

    if is_recorded(path, key):
        return Outcome(action="already recorded", **common)

    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Append-only, and the header is written once when the file is created.
        # Never `write_text` the whole file: a bug in this module must not be
        # able to cost what the 2026-08-15 overwrite cost.
        if not path.exists():
            path.write_text(_file_header(name))
        with path.open("a") as fh:
            fh.write("\n" + section)

    return Outcome(action="appended", **common)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python3 -m scripts.study_results",
        description="Append each study's current report to its tracked per-era "
                    "record under research/study-results/.")
    ap.add_argument("--study", metavar="NAME",
                    help="record one study instead of every study with a report")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be appended; write nothing")
    ap.add_argument("--include-refusals", action="store_true",
                    help="also record designed refusals (a study declining to "
                         "answer — its current status, not a result)")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR,
                    help=f"where the reports live (default: {OUT_DIR.relative_to(ROOT)})")
    ap.add_argument("--dest", type=Path, default=DEST_DIR,
                    help=f"where the records live (default: {DEST_DIR.relative_to(ROOT)})")
    args = ap.parse_args(argv)

    names = [args.study] if args.study else discover(args.out_dir)
    outcomes = [record(n, args.out_dir, args.dest, dry_run=args.dry_run,
                       include_refusals=args.include_refusals)
                for n in names]

    actions = ("appended", "already recorded", "skipped (refusal)", "no report")
    width = max((len(o.name) for o in outcomes), default=1)
    for out in outcomes:
        print(f"  {out.name:{width}s}  {out.action:18s}  {out.detail}")

    tally = {a: sum(1 for o in outcomes if o.action == a) for a in actions}
    verb = "would append" if args.dry_run else "appended"
    print(f"\n{len(outcomes)} studies: {verb} {tally['appended']}, "
          f"{tally['already recorded']} already recorded, "
          f"{tally['skipped (refusal)']} refusals skipped, "
          f"{tally['no report']} with no report")
    if tally["skipped (refusal)"] and not args.include_refusals:
        print("(--include-refusals records those too)")
    if args.dry_run:
        print("(--dry-run: nothing written)")
    else:
        rel = args.dest.relative_to(ROOT) if args.dest.is_relative_to(ROOT) else args.dest
        print(f"records in {rel}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
