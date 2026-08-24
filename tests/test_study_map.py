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
from scripts.study_map import build, catalog, digest, render, summary, tuning

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
    assert "lib/book.py" in catalog.INFRA


def test_every_study_has_a_known_family_and_state():
    for name, study in catalog.STUDIES.items():
        assert study.family in catalog.FAMILIES, name
        assert study.state in catalog.STATES, name
        assert study.question.endswith(("?", ".")), f"{name}: question reads oddly"
        assert study.verdict, name


def test_prose_companion_names_every_study():
    text = (ROOT / "research" / "study-map.md").read_text()
    missing = [n for n in catalog.STUDIES if n not in text]
    assert not missing, f"study-map.md does not mention: {missing}"


def test_retired_field_defaults_to_none():
    assert catalog.STUDIES["bear_deploy"].retired is None


def test_retired_studies_helper_matches_the_dataclass_field():
    assert catalog.retired_studies() == {
        n: s.retired for n, s in catalog.STUDIES.items() if s.retired
    }


def test_exactly_the_two_gitignored_scratch_studies_are_retired():
    """Pins the actual Part-B retirement, not just the mechanism — see
    research/next-steps.md §0c(B)."""
    assert set(catalog.retired_studies()) == {
        "combined_exit_study", "underlying_exit_study"}


def test_infra_table_matches_the_runners_infra_set():
    """catalog.INFRA is keyed by path relative to scripts/backtest_study/ — run.py at
    the package root, lib/<name>.py for everything under lib/ — while run.INFRA is
    keyed by bare module stem, minus dunders."""
    expected = {
        "run.py" if stem == "run" else f"lib/{stem}.py"
        for stem in study_runner.INFRA if not stem.startswith("__")
    } | {"lib/book.py"}
    assert set(catalog.INFRA) == expected


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


def test_retired_study_with_no_report_reads_as_retired_not_never_run(tmp_path):
    """The whole point of retiring a study is that it will NOT be run again —
    'never run' would read as 'nobody got round to it' instead."""
    run = summary.summarize("combined_exit_study", tmp_path)
    assert not run.ran
    assert run.retired is not None
    assert run.status == "retired"


def test_a_non_retired_study_with_no_report_is_unaffected(tmp_path):
    run = summary.summarize("bear_deploy", tmp_path)
    assert run.retired is None
    assert run.status == "never run"


def test_retired_study_with_an_actual_report_shows_its_real_status(tmp_path):
    """Retirement only overrides the ran=False case. A retired study CAN still
    be run directly (run.py prints a notice and runs it) — if it left a
    report, that report's own outcome is what's true, not a blanket 'retired'."""
    write_report(tmp_path, "combined_exit_study", "some body\n", rc=0)
    run = summary.summarize("combined_exit_study", tmp_path)
    assert run.ran and run.retired is not None
    assert run.status == "ok"


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


# ── designed refusals ─────────────────────────────────────────────────────────
#
# v4_bridge is the one study that declares DESIGNED_REFUSAL_EXIT_CODES = {2, 3}
# (scripts/backtest_study/f1_selection/v4_bridge.py) — these tests use its real name so the
# read goes through run.py's actual `_refusal_codes()`, the same reader
# `run --all` uses, rather than a mock of it.

def test_declared_refusal_reads_as_refused_not_ok_but_not_a_failure(tmp_path):
    body = ("ABORT: expected v3 then v4, got v3 then v3.\n"
            "  Refusing to compare a book against itself.\n")
    write_report(tmp_path, "v4_bridge", body, rc=3)
    run = summary.summarize("v4_bridge", tmp_path)

    assert not run.ok               # exit_code != 0, unchanged semantics
    assert run.refused is True
    assert run.status == "refused (exit 3)"
    assert run.excerpt_kind == "refusal"
    assert run.excerpt[0].startswith("ABORT:")


def test_declared_refusal_without_a_failure_shaped_message_is_still_a_refusal(tmp_path):
    """Not every designed refusal prints in the ABORT/Traceback shape
    _FAILURE looks for — e.g. v4_bridge's MIN_V4_DATES gate just prints a
    plain 'GATE NOT MET' paragraph. It must still classify as a refusal, not
    silently fall through to 'matched' or 'tail'."""
    body = "GATE NOT MET — v4 has 5 of 20 required dates.\n  15 more to go.\n"
    write_report(tmp_path, "v4_bridge", body, rc=2)
    run = summary.summarize("v4_bridge", tmp_path)

    assert run.refused is True
    assert run.status == "refused (exit 2)"
    assert run.excerpt_kind == "refusal"
    assert run.excerpt[0].startswith("GATE NOT MET")


def test_an_undeclared_exit_code_on_a_refusal_study_still_fails(tmp_path):
    """v4_bridge only declared {2, 3} — an exit 1 (a real crash) from the same
    study must NOT be swallowed by the refusal path."""
    body = "Traceback (most recent call last):\nValueError: boom\n"
    write_report(tmp_path, "v4_bridge", body, rc=1)
    run = summary.summarize("v4_bridge", tmp_path)

    assert run.refused is False
    assert run.status == "exit 1"
    assert run.excerpt_kind == "failure"


def test_a_study_with_no_declared_refusal_codes_never_reads_as_refused(tmp_path):
    write_report(tmp_path, "bear_deploy", "*** something broke ***\n", rc=1)
    run = summary.summarize("bear_deploy", tmp_path)

    assert run.refused is False
    assert run.status == "exit 1"
    assert run.excerpt_kind == "failure"


def test_extract_is_given_the_refusal_codes_directly():
    """Unit-level pin on extract() itself, independent of summarize()'s wiring."""
    body = ["ABORT: nope", "  detail"]
    excerpt, kind = summary.extract(body, 3, refusal_codes=frozenset({2, 3}))
    assert kind == "refusal"
    excerpt2, kind2 = summary.extract(body, 3, refusal_codes=frozenset())
    assert kind2 == "failure"
    assert excerpt == excerpt2  # same text either way — only the label differs


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


ABORT_BODY = """\
running

ABORT: expected v3 then v4, got v3 then v3.
  v3 exports carry score_flow/score_dealer; v4 exports do not.
  Refusing to compare a book against itself.

unrelated trailing chatter
"""


@pytest.mark.parametrize("rc, kind", [
    # 3 is an era refusal, inherited by EVERY study from lib/era.py (see
    # run._refusal_codes) — and this ABORT is exactly what emits it.
    (3, "refusal"),
    # 1 is nobody's designed code, so the same paragraph means a real failure.
    (1, "failure"),
])
def test_abort_paragraph_is_quoted_whether_it_refused_or_failed(tmp_path, rc, kind):
    """Same text, different verdict on what it means — the excerpt machinery
    must not care which, or a refusal would lose its explanation."""
    write_report(tmp_path, "demo", ABORT_BODY, rc=rc)
    run = summary.summarize("demo", tmp_path)
    assert run.excerpt_kind == kind
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


def test_page_marks_retired_studies_with_the_retired_pill_and_card_class(page):
    assert 'class="card is-reference is-retired"' in page   # combined_exit_study
    assert 'class="card is-null is-retired"' in page         # underlying_exit_study
    assert page.count('<span class="pill is-retired">retired</span>') == \
        len(catalog.retired_studies())


def test_page_shows_the_retirement_reason_as_a_caveat(page):
    assert "RETIRED 2026-08-14" in page
    assert "results_proxy.csv" in page               # combined_exit_study's reason
    assert "v2_BacktestResults_nocreditdiff.csv" in page  # underlying_exit_study's reason


def test_non_retired_study_gets_no_retired_pill(page):
    """bear_deploy is an ordinary, runnable study — its card must not claim
    retirement just because the page also renders retired ones."""
    idx = page.index('<h3>bear_deploy.py</h3>')
    head_end = page.index("</div>", idx)
    assert 'is-retired' not in page[idx:head_end]


def test_page_shows_refused_not_bad_styling_for_a_designed_refusal(tmp_path):
    for name in catalog.STUDIES:
        if name == "v4_bridge":
            write_report(tmp_path, name,
                        "ABORT: expected v3 then v4, got v3 then v3.\n", rc=3)
        else:
            write_report(tmp_path, name, VERDICT_BODY)
    md = tmp_path / "current.md"
    md.write_text("## 2026-08-12 — a thing happened\n\nprose.\n")
    out = build.build_fragment(out_dir=tmp_path, log_path=md)

    assert '<span class="refused">refused (exit 3)</span>' in out
    assert "BY DESIGN" in out
    # "exited", not "declared": most studies never name these codes — they
    # inherit the era pair from lib/era.py via run._refusal_codes, so claiming
    # the study declared them would send a reader hunting a constant that is
    # not in the file.
    assert "v4_bridge exited 3 as a designed refusal" in out
    # A refusal must never be indistinguishable from a real failure's styling.
    assert '<span class="bad">refused' not in out
    assert 'kind">— BY DESIGN' in out  # the excerpt's own kind-note, not "did not finish"
    # A refused card must route the reader to the era that COULD answer.
    # Without it the card is a dead end: reports are gitignored scratch, so the
    # record is the only place a past era's numbers survive.
    assert "research/study-results/f1_selection/v4_bridge.md" in out


def test_page_shows_retired_label_when_a_retired_study_has_no_report(tmp_path):
    retired = catalog.retired_studies()
    for name in catalog.STUDIES:
        if name in retired:
            continue  # leave unrun — the case under test
        write_report(tmp_path, name, VERDICT_BODY)
    md = tmp_path / "current.md"
    md.write_text("## 2026-08-12 — a thing happened\n\nprose.\n")
    out = build.build_fragment(out_dir=tmp_path, log_path=md)

    assert out.count('<span class="retired-label">retired</span>') == len(retired)
    for name in retired:
        card = out[out.index(f'<h3>{name}.py</h3>'):]
        head_end = card.index("</div>")
        # "never run" would understate it — it must read as retired instead.
        assert "never run" not in card[:head_end]


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
    non_retired = len(catalog.STUDIES) - len(catalog.retired_studies())
    # Retired studies with no report say "retired", not "never run" — see
    # test_page_shows_retired_label_when_a_retired_study_has_no_report.
    assert out.count("never run") >= non_retired
    assert out.count('<span class="retired-label">retired</span>') == \
        len(catalog.retired_studies())
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


def test_built_page_is_a_document():
    """`site/` is gitignored, so the page may legitimately not exist yet."""
    if not build.DEST.exists():
        pytest.skip("no site/study-map.html — run `make study-map`")
    assert "<title>" in build.DEST.read_text()


# ── digest pages ──────────────────────────────────────────────────────────────
def test_digest_site_name_is_hyphenated():
    assert render.site_name("account_sim") == "account-sim-digest.html"


def test_digest_write_all_skips_studies_with_no_digest(tmp_path):
    written = digest.write_all(tmp_path / "out", tmp_path / "site")
    assert written == []
    site_dir = tmp_path / "site"
    assert not list(site_dir.glob("*.html")) if site_dir.exists() else True


def test_digest_strips_a_whole_file_wrapping_fence(tmp_path):
    name = next(iter(catalog.STUDIES))
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    md_path = out_dir / f"{name}-digest-latest.md"
    md_path.write_text(
        "```markdown\n"
        "# Heading\n\n"
        "A normal paragraph of prose.\n"
        "```\n")
    out = digest.page(name, md_path)
    assert "<h1>Heading</h1>" in out
    assert "```" not in out


def test_digest_page_is_linked_from_its_study_card(tmp_path):
    name = next(iter(catalog.STUDIES))
    out_dir = tmp_path
    write_report(out_dir, name, VERDICT_BODY)
    (out_dir / f"{name}-digest-latest.md").write_text("# A Digest Title\n\nSome prose.\n")
    fragment = build.build_fragment(out_dir=out_dir, log_path=tmp_path / "absent.md")
    assert f'href="{render.site_name(name)}"' in fragment
