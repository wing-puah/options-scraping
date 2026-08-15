"""Tests for scripts/study_results — the tracked per-(study, era) record.

This module exists because `backtests/study_output/` is gitignored scratch that
was overwritten on 2026-08-15 with nothing to recover from, and because the
standing policy ("a study runs on the CURRENT era only") guarantees that v3's
reports will be replaced by v4's the moment v4 matures. The record is the only
thing that will still be able to answer "what did this study say on v3?".

That gives the tests three jobs, and they are different in kind:

  * **Append-only-ness.** The failure mode this whole folder exists to prevent
    is a result silently disappearing. So: a new (era, sha) appends; an
    unchanged re-run appends NOTHING; a different era appends a SECOND section
    rather than replacing the first; a different sha for the same era does too,
    because the code that produced a number is part of what the number means.
  * **Honesty of the quote.** CLAUDE.md's research-tier rule is that last-run
    excerpts are quoted verbatim, never paraphrased. The pin here is byte
    equality with what `summary.summarize()` returned — not "contains", not
    "looks similar" — because a record read years later has no report left to
    check it against.
  * **Harmlessness.** `--dry-run` must write nothing at all, and a study with no
    report on disk must be skipped quietly (a retired study is never run again
    by design, and a fresh checkout has no reports at all).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from scripts import study_results
from scripts.backtest_study import run as study_runner
from scripts.study_map import summary

ROOT = Path(__file__).resolve().parents[1]

# A REAL study, deliberately — the record tree mirrors `scripts/backtest_study/`
# by reading the study module's own parent folder, so a made-up name like "demo"
# would quietly exercise the unfiled fallback instead of the mirror these tests
# are here to hold in place.
STUDY = "bear_arm"
FAMILY = "f1_selection"


# ── fixtures ──────────────────────────────────────────────────────────────────
# Deliberately the same report shape test_study_map.py builds, plus the `era`
# line that shipped on 2026-08-15 — this module keys on that line, so a fixture
# without it would test a report shape the recorder never sees in practice.
HEADER = """\
==============================================================================
STUDY: {name}
==============================================================================
  run at    2026-08-15 23:45:14
  command   python -m scripts.backtest_study.f1_selection.{name}
  git       {sha} (main, working tree dirty)
  python    3.11.2
  era       {era} (prefixed exports)
  inputs:
   1,926 rows  2026-08-15 19:03  backtests/to_evaluate/analysis - v3_BacktestResults.csv
   4,533 rows  2026-08-15 19:03  backtests/to_evaluate/analysis - v3_BacktestProxy.csv
  {rows} rows  2026-08-15 19:03  backtests/to_evaluate/analysis - v3_AnalysisClaude.csv
==============================================================================
"""

FOOTER = """
==============================================================================
exit code {rc} after {secs}s
==============================================================================
"""

VERDICT_BODY = """\
==============================================================================
VERDICT
==============================================================================
  the ladder is at the ceiling of this data
  gain -0.155 CI95 [-0.314, -0.001]
"""


def write_report(out_dir: Path, name: str, body: str = VERDICT_BODY,
                 era: str = "v3", sha: str = "53b7167", rows: str = "11,836",
                 rc: int = 0, secs: str = "12.4") -> Path:
    """`rows` is the analysis export's row count — the thing that moves when an
    era ACCRUES dates without a commit, and the reason the key fingerprints the
    input counts as well as the era and the sha."""
    path = out_dir / f"{name}-latest.txt"
    path.write_text(HEADER.format(name=name, era=era, sha=sha, rows=rows)
                    + body + FOOTER.format(rc=rc, secs=secs))
    return path


def record(tmp_path: Path, name: str = STUDY, **kw):
    """`record()` against a scratch report dir AND a scratch destination."""
    return study_results.record(name, out_dir=tmp_path / "out",
                                dest_dir=tmp_path / "rec",
                                today=date(2026, 8, 15), **kw)


def setup_dirs(tmp_path: Path) -> tuple[Path, Path]:
    out, rec = tmp_path / "out", tmp_path / "rec"
    out.mkdir()
    return out, rec


# ── a new result is recorded ──────────────────────────────────────────────────
def test_a_new_result_appends_a_section_headed_by_its_whole_key(tmp_path):
    out, rec = setup_dirs(tmp_path)
    write_report(out, STUDY)

    outcome = record(tmp_path)

    assert outcome.action == "appended"
    assert (outcome.key.era, outcome.key.sha) == ("v3", "53b7167")
    text = (rec / FAMILY / f"{STUDY}.md").read_text()
    assert text.startswith(f"# {STUDY} — per-era record")
    # The heading carries all three fields, not just the era: two sections of
    # one era are routine now, and the marker that distinguishes them renders
    # as nothing.
    assert (f"## era v3 · inputs {outcome.key.inputs} · sha 53b7167 "
            f"— recorded 2026-08-15") in text
    assert f"<!-- key era=v3 sha=53b7167 inputs={outcome.key.inputs} -->" in text


def test_the_section_states_the_facts_the_report_carried(tmp_path):
    """Population, run line and command come from the header — and only from it.

    Nothing on these lines is computed by this module; a figure appearing here
    that the report did not print would be exactly the kind of quiet invention
    the research tier forbids.
    """
    out, _rec = setup_dirs(tmp_path)
    write_report(out, STUDY)

    section = record(tmp_path).section

    assert "1,926 results · 4,533 proxy · 11,836 analysis" in section
    assert "(inputs dated 2026-08-15 19:03)" in section
    assert "run         2026-08-15 23:45:14 · git 53b7167 (main, working tree dirty)" in section
    assert "exit 0 · 12.4s" in section
    assert f"command     python -m scripts.backtest_study.f1_selection.{STUDY}" in section
    assert "excerpt     verdict" in section


# ── idempotency and append-only-ness ──────────────────────────────────────────
def test_rerunning_with_nothing_changed_appends_nothing(tmp_path):
    """The record is append-only, so a no-op re-run must be a genuine no-op:
    not a duplicate section, and not a rewritten one."""
    out, rec = setup_dirs(tmp_path)
    write_report(out, STUDY)

    assert record(tmp_path).action == "appended"
    before = (rec / FAMILY / f"{STUDY}.md").read_text()

    second = record(tmp_path)

    assert second.action == "already recorded"
    assert (rec / FAMILY / f"{STUDY}.md").read_text() == before


def test_a_different_era_appends_a_second_section(tmp_path):
    """The comparison this folder exists to enable. v4's answer is recorded
    ALONGSIDE v3's — the v3 section is still there afterwards, because by the
    time v4 runs its v3 report has been overwritten and this is the only copy."""
    out, rec = setup_dirs(tmp_path)
    write_report(out, STUDY, era="v3")
    record(tmp_path)

    write_report(out, STUDY, era="v4")
    outcome = record(tmp_path)

    assert outcome.action == "appended"
    text = (rec / FAMILY / f"{STUDY}.md").read_text()
    assert "<!-- key era=v3 sha=53b7167 inputs=" in text
    assert "<!-- key era=v4 sha=53b7167 inputs=" in text
    assert text.index("era=v3") < text.index("era=v4")   # newest last


def test_a_different_sha_on_the_same_era_appends_a_second_section(tmp_path):
    """Same population, different code, therefore a different result — the same
    discipline the provenance header encodes by printing the sha at all. A
    recorder keyed on era alone would silently drop the re-run."""
    out, rec = setup_dirs(tmp_path)
    write_report(out, STUDY, sha="53b7167")
    record(tmp_path)

    write_report(out, STUDY, sha="abc1234")
    outcome = record(tmp_path)

    assert outcome.action == "appended"
    text = (rec / FAMILY / f"{STUDY}.md").read_text()
    assert "<!-- key era=v3 sha=53b7167 inputs=" in text
    assert "<!-- key era=v3 sha=abc1234 inputs=" in text
    assert text.count("## era v3") == 2


def test_a_report_with_no_era_line_is_recorded_as_unknown_never_guessed(tmp_path):
    """A pre-2026-08-15 report genuinely does not record its population. Reading
    that silence as "v3" is the exact mistake that let a v4 re-export be quoted
    under fourteen v3 verdicts."""
    out, rec = setup_dirs(tmp_path)
    path = write_report(out, STUDY)
    path.write_text("\n".join(ln for ln in path.read_text().splitlines()
                              if not ln.startswith("  era ")))

    outcome = record(tmp_path)

    assert outcome.key.era == "unknown"
    text = (rec / FAMILY / f"{STUDY}.md").read_text()
    assert "<!-- key era=unknown sha=53b7167 inputs=" in text
    assert "predates the era header" in text


# ── the anti-paraphrase pin ───────────────────────────────────────────────────
def test_the_excerpt_is_byte_identical_to_what_summarize_returned(tmp_path):
    """THE pin. Not "contains", not "similar" — the quoted block must be exactly
    the lines `summary.summarize()` pulled out of the report, in order, with no
    re-wording, re-wrapping, re-indenting or trimming. Anyone reading this file
    in a later era has no report left to check it against, so the quote is the
    evidence rather than a pointer to it.
    """
    out, rec = setup_dirs(tmp_path)
    write_report(out, STUDY)
    run = summary.summarize(STUDY, out)
    assert run.excerpt_kind == "verdict" and run.excerpt

    record(tmp_path)
    text = (rec / FAMILY / f"{STUDY}.md").read_text()

    quoted = text.split("```")[1].splitlines()
    quoted = [ln for ln in quoted if ln != ""]
    assert quoted == run.excerpt


def test_a_designed_refusal_is_labelled_as_one_not_as_a_failure(tmp_path):
    """v4_bridge's real name, so the refusal codes come from run.py's own
    `_refusal_codes()`. A pre-registered gate declining to answer is correct
    behaviour, and a record that filed it as a break would be worse than no
    record: it would read as a study that used to crash."""
    out, rec = setup_dirs(tmp_path)
    write_report(out, "v4_bridge", body="GATE NOT MET — v4 has 14 of 20 dates.\n", rc=2)

    outcome = refuser(out, rec, include_refusals=True)

    assert outcome.excerpt_kind == "refusal"
    text = (rec / "f1_selection" / "v4_bridge.md").read_text()
    assert "exit 2 (designed refusal)" in text
    assert "excerpt     refusal" in text


# ── the input fingerprint ─────────────────────────────────────────────────────
#
# The defect these pin: an era is not a fixed dataset, it ACCRUES dates while
# the code stands still. Keyed on (era, sha) alone, v4's "too thin, refusing"
# run would claim the key, and the first REAL v4 result a month later — with no
# commit in between, because none is needed — would be dropped as "already
# recorded". That is the one outcome this whole folder exists to prevent.

def test_the_same_era_and_sha_on_a_bigger_book_appends_a_second_section(tmp_path):
    """THE regression pin. Same era, same code, more dates -> a new result."""
    out, rec = setup_dirs(tmp_path)
    write_report(out, STUDY, era="v4", rows="1,306")     # v4 as it is today
    first = record(tmp_path)

    write_report(out, STUDY, era="v4", rows="9,940")     # v4 a month later
    second = record(tmp_path)

    assert first.action == "appended" and second.action == "appended"
    assert first.key.era == second.key.era
    assert first.key.sha == second.key.sha
    assert first.key.inputs != second.key.inputs
    text = (rec / FAMILY / f"{STUDY}.md").read_text()
    assert text.count("## era v4") == 2


def test_the_fingerprint_ignores_mtimes_so_a_no_op_re_export_is_not_a_new_result(tmp_path):
    """Row counts, not mtimes. A re-export of unchanged data moves every mtime
    while the book stays identical; recording that as a fresh result would be
    noise, and noise is what makes a genuine change hard to spot."""
    out, _rec = setup_dirs(tmp_path)
    path = write_report(out, STUDY)
    record(tmp_path)

    path.write_text(path.read_text().replace("2026-08-15 19:03", "2026-08-16 08:00"))

    assert record(tmp_path).action == "already recorded"


def test_the_fingerprint_does_not_depend_on_the_order_the_inputs_were_listed(tmp_path):
    """The runner listing its inputs in another order is not a different book."""
    out, _rec = setup_dirs(tmp_path)
    path = write_report(out, STUDY)
    forward = study_results.fingerprint(summary.summarize(STUDY, out))

    lines = path.read_text().splitlines()
    head = lines.index("  inputs:") + 1
    lines[head:head + 3] = list(reversed(lines[head:head + 3]))
    path.write_text("\n".join(lines) + "\n")

    assert study_results.fingerprint(summary.summarize(STUDY, out)) == forward


def test_a_legacy_marker_without_a_fingerprint_still_suppresses_a_re_append(tmp_path):
    """BACK-COMPAT. The nineteen era-v3 sections on disk were written before the
    key grew its third field, and they are the ONLY surviving copy of those
    reports — the scratch was overwritten hours later. A fingerprint-less marker
    therefore matches any fingerprint for its (era, sha), so a re-run recognises
    them instead of appending a duplicate beside each.
    """
    out, rec = setup_dirs(tmp_path)
    write_report(out, STUDY)
    legacy = rec / FAMILY / f"{STUDY}.md"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("# legacy\n\n## era v3 — recorded 2026-08-15\n"
                      "<!-- key era=v3 sha=53b7167 -->\n")
    before = legacy.read_text()

    assert record(tmp_path).action == "already recorded"
    assert legacy.read_text() == before

    # ...and the clause is scoped to the fingerprint alone. A legacy marker
    # must NOT swallow a different era or a different sha.
    write_report(out, STUDY, era="v4")
    assert record(tmp_path).action == "appended"


def test_the_key_marker_is_parsed_as_a_field_bag_not_a_fixed_shape(tmp_path):
    """The key has already had to grow once. An unknown extra field must not
    stop a marker being recognised, or the next growth re-appends the lot."""
    key = study_results.SectionKey(era="v5", sha="deadbee", inputs="abc1234")
    path = tmp_path / "rec.md"
    path.write_text("<!-- key era=v5 sha=deadbee inputs=abc1234 future=xyz -->\n")

    assert study_results.is_recorded(path, key)


# ── refusals are status, not result ───────────────────────────────────────────
def refuser(out: Path, rec: Path, **kw):
    """`record()` for v4_bridge — the one study whose real refusal codes make a
    non-zero exit classify as a refusal rather than a failure."""
    return study_results.record("v4_bridge", out_dir=out, dest_dir=rec,
                                today=date(2026, 8, 15), **kw)


def test_a_designed_refusal_is_skipped_by_default(tmp_path):
    """A refusal is the study's correct current STATUS, not a RESULT. Twenty
    near-identical "era too thin" sections would bury the findings the folder
    exists to keep, and they say nothing a glance at the era does not.

    Safe to skip ONLY because of the fingerprint: the real result that arrives
    once the era thickens keys differently from the refusal, so it records
    either way — this is signal-to-noise, not correctness.
    """
    out, rec = setup_dirs(tmp_path)
    write_report(out, "v4_bridge", body="REFUSED — era v4 has 10 dates.\n", rc=2)

    outcome = refuser(out, rec)

    assert outcome.action == "skipped (refusal)"
    assert not rec.exists()


def test_include_refusals_records_them_for_the_audit_trail(tmp_path):
    out, rec = setup_dirs(tmp_path)
    write_report(out, "v4_bridge", body="REFUSED — era v4 has 10 dates.\n", rc=2)

    assert refuser(out, rec, include_refusals=True).action == "appended"
    assert (rec / "f1_selection" / "v4_bridge.md").exists()
    # ...and is itself idempotent, on the same key as everything else.
    assert refuser(out, rec, include_refusals=True).action == "already recorded"


def test_a_real_failure_is_still_recorded_even_though_a_refusal_is_not(tmp_path):
    """The skip is scoped to DECLARED refusals. An undeclared non-zero exit is a
    real break, it is rare, and someone reading the record a year later should
    see that the study was broken rather than find a silent gap."""
    out, rec = setup_dirs(tmp_path)
    write_report(out, STUDY, body="*** HARNESS VALIDATION FAILED — stopping. ***\n", rc=1)

    outcome = record(tmp_path)

    assert outcome.excerpt_kind == "failure"
    assert outcome.action == "appended"


# ── harmlessness ──────────────────────────────────────────────────────────────
def test_dry_run_writes_nothing(tmp_path):
    out, rec = setup_dirs(tmp_path)
    write_report(out, STUDY)

    outcome = record(tmp_path, dry_run=True)

    assert outcome.action == "appended"       # what it WOULD do
    assert outcome.section                    # ...and the text it would write
    assert not rec.exists()                   # but nothing on disk


def test_dry_run_after_a_real_record_still_reports_it_as_already_recorded(tmp_path):
    out, _rec = setup_dirs(tmp_path)
    write_report(out, STUDY)
    record(tmp_path)

    assert record(tmp_path, dry_run=True).action == "already recorded"


def test_a_study_with_no_report_is_skipped_without_error(tmp_path):
    """Not an error state: a retired study is never run again by design, and a
    fresh checkout has no reports at all until something is run."""
    _out, rec = setup_dirs(tmp_path)

    outcome = record(tmp_path, name="combined_exit_study")

    assert outcome.action == "no report"
    assert not rec.exists()


# ── the mirror ────────────────────────────────────────────────────────────────
def test_every_records_folder_equals_its_modules_folder():
    """THE anti-drift pin for the tree itself.

    `research/study-results/` mirrors `scripts/backtest_study/` so the records
    read in the order a play moves through the system — f1 pick it, f2 manage
    it, f3 wrap it, f4 fund it. The mirror only stays true if the folder is
    DERIVED from the module's actual location, so this asserts exactly that
    equality for every study the runner knows about. A hardcoded name -> folder
    table, or one keyed off `catalog.STUDIES[...].family`, would pass on the day
    it was written and rot the first time a study moved.
    """
    for name, module in study_runner.study_paths().items():
        if name in study_results.NON_STUDY_STEMS:
            continue           # lib/book.py — the runner's diagnostic, not a study
        assert study_results.family_of(name) == module.parent.name, name
        assert study_results.record_path(name).parent.name == module.parent.name, name


def test_an_arm_stem_files_under_its_base_studys_family():
    """`account_sim-compounding` is not a module, so its folder comes from
    `account_sim` — one rule (`base_study`) shared with discovery, not a second
    one that could put an arm somewhere its parent study is not."""
    assert study_results.base_study("account_sim-compounding") == "account_sim"
    assert study_results.family_of("account_sim-compounding") == "f4_deployment"
    assert study_results.family_of("account_sim") == "f4_deployment"


def test_an_unknown_stem_is_filed_as_unfiled_never_guessed_into_a_family():
    """A report whose study module has since been deleted or renamed has no
    family. Filing it visibly as unfiled beats putting it in a plausible-looking
    folder that is simply wrong."""
    assert study_results.family_of("no_such_study") == study_results.UNFILED


# ── discovery ─────────────────────────────────────────────────────────────────
def test_discover_covers_the_catalog_plus_any_arm_stem_on_disk(tmp_path):
    """Arms (`account_sim-compounding`, …) file their results under their own
    stem and are just as era-bound as the base study, so they get their own
    record. `book` is the runner's --validate diagnostic, not a study."""
    out, _rec = setup_dirs(tmp_path)
    write_report(out, "account_sim-compounding")
    write_report(out, "book")

    names = study_results.discover(out)

    assert "account_sim-compounding" in names
    assert "book" not in names
    assert set(study_results.catalog.STUDIES) <= set(names)


def test_the_shipped_readme_explains_the_folder(tmp_path):
    """The folder is tracked and hand-read; a record with no README is a
    directory of fixed-width fragments nobody can date or trust."""
    text = (ROOT / "research" / "study-results" / "README.md").read_text()
    assert "append-only" in text.lower()
    assert "verbatim" in text.lower()
    assert "current.md" in text
