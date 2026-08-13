"""Tests for scripts/study_map — the readable map of the backtest-study package.

Two things are worth guarding, and they are different in kind:

  * **Drift.** The map's verdicts are hand-written. A new study file that nobody
    described is a map that quietly lies by omission, so the catalog must cover
    exactly the runner's own study list, and the prose companion must name each
    one.
  * **Honesty of the quoted half.** The last-run block quotes reports. It must
    never present the tail of a report as a verdict, never invent a number, and
    never turn a failed run into a green one.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.backtest_study import run as study_runner
from scripts.study_map import build, catalog, render, summary, tuning

ROOT = Path(__file__).resolve().parents[1]


# ── fixtures ──────────────────────────────────────────────────────────────────
HEADER = """\
==============================================================================
STUDY: {name}
==============================================================================
  run at    2026-08-13 15:51:31
  command   python -m scripts.backtest_study.{name}
  git       309c564 (main, working tree dirty)
  python    3.11.2
  inputs:
   1,926 rows  2026-08-11 15:38  backtests/to_evaluate/analysis - BacktestResults.csv
     803 rows  2026-08-13 11:56  backtests/mech_regime/spy_vix_daily_full.csv
==============================================================================
"""

FOOTER = """
==============================================================================
exit code {rc} after {secs}s
==============================================================================
"""


def write_report(out_dir: Path, name: str, body: str, rc: int = 0,
                 secs: str = "1.5") -> Path:
    path = out_dir / f"{name}-latest.txt"
    path.write_text(HEADER.format(name=name) + body + FOOTER.format(rc=rc, secs=secs))
    return path


# ── drift guards ──────────────────────────────────────────────────────────────
def test_catalog_covers_exactly_the_runners_study_list():
    """A new study file must be described before the suite goes green again.

    `book` is the one runnable name that is not a study — the runner lists it
    for its `--validate` diagnostics, and the map files it under infrastructure.
    """
    assert set(catalog.STUDIES) | {"book"} == set(study_runner.discover())
    assert "book.py" in catalog.INFRA


def test_every_study_has_a_known_family_and_state():
    for name, study in catalog.STUDIES.items():
        assert study.family in catalog.FAMILIES, name
        assert study.state in catalog.STATES, name
        assert study.question.endswith(("?", ".")), f"{name}: question reads oddly"
        assert study.verdict, name


def test_prose_companion_names_every_study():
    text = (ROOT / "config" / "backtest-tuning" / "study-map.md").read_text()
    missing = [n for n in catalog.STUDIES if n not in text]
    assert not missing, f"study-map.md does not mention: {missing}"


def test_infra_table_matches_the_runners_infra_set():
    """catalog.INFRA is keyed by filename; run.INFRA by module stem, minus dunders."""
    catalogued = {name.removesuffix(".py") for name in catalog.INFRA}
    expected = {n for n in study_runner.INFRA if not n.startswith("__")} | {"book"}
    assert catalogued == expected


# ── report parsing ────────────────────────────────────────────────────────────
def test_header_and_footer_are_parsed(tmp_path):
    write_report(tmp_path, "demo", "some body\n", rc=0, secs="12.3")
    run = summary.summarize("demo", tmp_path)

    assert run.ran and run.ok
    assert run.run_at == "2026-08-13 15:51:31"
    assert run.git_sha == "309c564"
    assert run.dirty is True
    assert run.elapsed == "12.3s"
    assert run.inputs[0][0] == "1,926"
    assert run.inputs[0][2].endswith("BacktestResults.csv")
    assert run.status == "ok"


def test_missing_report_is_reported_as_never_run(tmp_path):
    run = summary.summarize("nothing_here", tmp_path)
    assert not run.ran
    assert run.status == "never run"
    assert run.excerpt == []


def test_missing_input_lines_are_surfaced(tmp_path):
    path = write_report(tmp_path, "demo", "body\n")
    path.write_text(path.read_text().replace(
        "     803 rows  2026-08-13 11:56  backtests/mech_regime/spy_vix_daily_full.csv",
        "  MISSING  backtests/mech_regime/spy_vix_daily_full.csv"))
    run = summary.summarize("demo", tmp_path)
    assert run.missing_inputs == ["backtests/mech_regime/spy_vix_daily_full.csv"]


def test_nonzero_exit_never_reads_as_ok(tmp_path):
    write_report(tmp_path, "demo", "*** HARNESS VALIDATION FAILED — stopping. ***\n", rc=1)
    run = summary.summarize("demo", tmp_path)
    assert not run.ok
    assert run.status == "exit 1"


# ── excerpt extraction ────────────────────────────────────────────────────────
VERDICT_BODY = """\
some working
==============================================================================
VERDICT (pre-registered rules)
==============================================================================
  B1 KEEP-CONDITIONED: NOT met — 0 subset(s) passed all criteria
  B2 EXIT FIX: shipped
"""


def test_banner_verdict_block_wins(tmp_path):
    write_report(tmp_path, "demo", VERDICT_BODY)
    run = summary.summarize("demo", tmp_path)
    assert run.excerpt_kind == "verdict"
    assert run.excerpt[0].startswith("VERDICT")
    assert any("B1 KEEP-CONDITIONED" in ln for ln in run.excerpt)


def test_last_verdict_block_wins_when_several(tmp_path):
    body = VERDICT_BODY + """
==============================================================================
VERDICT (second pass)
==============================================================================
  the later one is the one that counts
"""
    write_report(tmp_path, "demo", body)
    run = summary.summarize("demo", tmp_path)
    assert "second pass" in run.excerpt[0]


def test_failure_excerpt_quotes_the_abort_paragraph(tmp_path):
    body = """\
running

ABORT: expected v3 then v4, got v3 then v3.
  v3 exports carry score_flow/score_dealer; v4 exports do not.
  Refusing to compare a book against itself.

unrelated trailing chatter
"""
    write_report(tmp_path, "demo", body, rc=3)
    run = summary.summarize("demo", tmp_path)
    assert run.excerpt_kind == "failure"
    assert run.excerpt[0].startswith("ABORT:")
    assert len(run.excerpt) == 3  # the abort line plus its own two lines, then the blank


def test_traceback_final_line_is_the_failure_excerpt(tmp_path):
    body = """\
Traceback (most recent call last):
  File "x.py", line 1, in <module>
FileNotFoundError: [Errno 2] No such file or directory: 'backtests/results_proxy.csv'
"""
    write_report(tmp_path, "demo", body, rc=1)
    run = summary.summarize("demo", tmp_path)
    assert run.excerpt_kind == "failure"
    assert run.excerpt[0].startswith("FileNotFoundError")


def test_criterion_lines_are_used_when_there_is_no_verdict_block(tmp_path):
    body = """\
  P1 worst-decile: n= 21  meanR +0.262  CI [-0.273, +0.730]   -> not met
  P2 correlation with deployed sleeve: -0.089 over 84 dates   -> MET
"""
    write_report(tmp_path, "demo", body)
    run = summary.summarize("demo", tmp_path)
    assert run.excerpt_kind == "matched"
    assert len(run.excerpt) == 2


def test_tail_is_labelled_as_tail_not_as_a_verdict(tmp_path):
    body = "\n".join(f"  row {i}  n= {i}  meanR +0.1" for i in range(20)) + "\n"
    write_report(tmp_path, "demo", body)
    run = summary.summarize("demo", tmp_path)
    assert run.excerpt_kind == "tail"
    assert "not a conclusion" in render._KIND_NOTE["tail"]


def test_tail_drops_banner_rules_and_end_marker(tmp_path):
    body = """\
  real line one
  real line two
====================================================================
END OF REPORT
====================================================================
"""
    write_report(tmp_path, "demo", body)
    run = summary.summarize("demo", tmp_path)
    assert run.excerpt == ["  real line one", "  real line two"]


def test_long_lines_are_clipped_not_wrapped(tmp_path):
    write_report(tmp_path, "demo", "  " + "x" * 400 + "\n")
    run = summary.summarize("demo", tmp_path)
    assert len(run.excerpt[0]) <= summary.MAX_LINE_CHARS
    assert run.excerpt[0].endswith("…")


def test_excerpt_is_bounded(tmp_path):
    body = ("==============================================================\n"
            "VERDICT\n"
            "==============================================================\n"
            + "".join(f"  line {i}\n" for i in range(50)))
    write_report(tmp_path, "demo", body)
    run = summary.summarize("demo", tmp_path)
    assert len(run.excerpt) <= summary.MAX_EXCERPT_LINES


def test_digest_title_is_quoted_from_the_digest_not_composed(tmp_path):
    write_report(tmp_path, "demo", "body\n")
    (tmp_path / "demo-digest-latest.md").write_text(
        "# Plain-Language Digest: Can This Run on $25,000?\n\nbody text\n")
    run = summary.summarize("demo", tmp_path)
    assert run.digest_title == "Plain-Language Digest: Can This Run on $25,000?"


def test_charts_page_is_linked_when_present(tmp_path):
    write_report(tmp_path, "demo", "body\n")
    (tmp_path / "demo-charts-latest.html").write_text("<title>x</title>")
    assert summary.summarize("demo", tmp_path).charts_path is not None


def test_a_file_without_the_runner_header_still_yields_a_tail(tmp_path):
    (tmp_path / "demo-latest.txt").write_text("just\nsome\nlines\n")
    run = summary.summarize("demo", tmp_path)
    assert run.ran and run.excerpt_kind == "tail"
    assert run.exit_code is None and run.status == "incomplete"
    assert run.run_at  # falls back to the file mtime


# ── tuning log ────────────────────────────────────────────────────────────────
def test_log_entries_are_quoted_newest_first(tmp_path):
    md = tmp_path / "current.md"
    md.write_text("""\
## 2026-08-01 — older thing happened

**Request:** something older.

## 2026-08-12 — `be_after` grid RUN: does NOT ship

The give-back pattern is in the underlying.

## no date on this one

body.
""")
    entries = tuning.read_log(md, limit=5)
    assert [e.date for e in entries] == ["2026-08-12", "2026-08-01", ""]
    assert entries[0].title == "`be_after` grid RUN: does NOT ship".replace("`", "")
    assert entries[0].gist == "The give-back pattern is in the underlying."


def test_log_gist_skips_tables_and_bullets(tmp_path):
    md = tmp_path / "current.md"
    md.write_text("## 2026-08-12 — thing\n\n| a | b |\n|---|---|\n- bullet\n\nreal prose here.\n")
    assert tuning.read_log(md)[0].gist == "real prose here."


def test_missing_log_is_not_an_error(tmp_path):
    assert tuning.read_log(tmp_path / "nope.md") == []
    assert tuning.log_mtime(tmp_path / "nope.md") == ""


# ── page ──────────────────────────────────────────────────────────────────────
@pytest.fixture
def page(tmp_path):
    for name in catalog.STUDIES:
        write_report(tmp_path, name, VERDICT_BODY)
    md = tmp_path / "current.md"
    md.write_text("## 2026-08-12 — a thing happened\n\nprose.\n")
    return build.build_fragment(out_dir=tmp_path, log_path=md)


def test_page_names_every_study_and_family(page):
    for name in catalog.STUDIES:
        assert f"{name}.py" in page
    for fam in catalog.FAMILIES.values():
        assert fam["title"] in page


def test_diagram_draws_every_family_with_its_real_count(page):
    """The lane boxes were once computed and never inserted — nothing else caught it."""
    for key, fam in catalog.FAMILIES.items():
        n = sum(1 for s in catalog.STUDIES.values() if s.family == key)
        assert f"{fam['index']} {fam['title'].upper()}" in page
        assert f"{n} STUDIES" in page


def test_page_carries_both_themes_for_every_token(page):
    """A colour defined only inside a media/[data-theme] block renders unreadable."""
    light = set(re.findall(r"^\s*(--[a-z-]+):", page, re.M))
    dark = set(re.findall(r"^\s*(--[a-z-]+):", page.split('[data-theme="dark"]')[1], re.M))
    assert dark <= light
    assert "--ink" in dark and "--paper" in dark


def test_page_separates_written_verdicts_from_quoted_runs(page):
    assert "verdicts: hand-written" in page
    assert "run blocks: quoted" in page


def test_page_escapes_report_text(tmp_path):
    write_report(tmp_path, list(catalog.STUDIES)[0], "  <script>alert(1)</script>\n")
    for name in list(catalog.STUDIES)[1:]:
        write_report(tmp_path, name, "body\n")
    out = build.build_fragment(out_dir=tmp_path, log_path=tmp_path / "absent.md")
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_never_run_studies_say_so_rather_than_showing_nothing(tmp_path):
    out = build.build_fragment(out_dir=tmp_path, log_path=tmp_path / "absent.md")
    assert out.count("never run") >= len(catalog.STUDIES)
    assert "No report on disk" in out


def test_failed_run_carries_the_gate_caveat(tmp_path):
    for name in catalog.STUDIES:
        write_report(tmp_path, name, "*** FAILED ***\n", rc=1)
    out = build.build_fragment(out_dir=tmp_path, log_path=tmp_path / "absent.md")
    assert "exited non-zero" in out
    assert "the gate working" in out


def test_write_produces_a_standalone_document(tmp_path):
    dest = build.write(tmp_path / "study-map.html", out_dir=tmp_path,
                       log_path=tmp_path / "absent.md")
    text = dest.read_text()
    assert text.startswith("<!doctype html>")
    assert text.rstrip().endswith("</html>")
    assert "<title>" in text


def test_fragment_mode_omits_the_document_wrapper(tmp_path):
    dest = build.write(tmp_path / "frag.html", out_dir=tmp_path,
                       log_path=tmp_path / "absent.md", standalone=False)
    assert not dest.read_text().startswith("<!doctype")


def test_refresh_quietly_never_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "build_fragment",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert build.refresh_quietly(tmp_path / "out.html") is None


def test_checked_in_page_is_current():
    """`docs/study-map.html` is generated but tracked — it must not go stale."""
    assert build.DEST.exists(), "run `make study-map`"
    assert "<title>" in build.DEST.read_text()
