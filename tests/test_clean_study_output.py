from pathlib import Path

from clean_study_output import Citation, cited_files, classify


# The runner's provenance header, which is what the stale check parses. The
# banner rules are load-bearing — study_charts.report splits sections on them.
_RULE = "=" * 78


def _report(study: str, sha: str, run_at: str) -> str:
    return (f"{_RULE}\n"
            f"STUDY: {study}\n"
            f"{_RULE}\n"
            f"  run at    {run_at}\n"
            f"  command   python -m scripts.backtest_study.{study}\n"
            f"  git       {sha} (main, working tree dirty)\n"
            f"  python    3.11.2\n"
            f"{_RULE}\n"
            f"  body\n"
            f"{_RULE}\n"
            f"exit code 0 after 1.0s\n"
            f"{_RULE}\n")


def _mkdir(tmp_path: Path, files: dict[str, str]) -> Path:
    out = tmp_path / "study_output"
    out.mkdir()
    for name, body in files.items():
        (out / name).write_text(body)
    return out


# A directory shaped like the real one: two studies with stamped runs plus their
# -latest.txt copy, and the pre-runner debris that never followed the convention.
_FILES = {
    "bear_arm-20260811-185851.txt": "old run\n",
    "bear_arm-20260812-112717.txt": "newer run\n",
    "bear_arm-latest.txt": "newer run\n",
    "book-20260811-185757.txt": "book run\n",
    "book-latest.txt": "book run\n",
    "bear_arm.txt": "pre-runner tee output\n",
    "run.txt": "pre-runner tee output\n",
    "mech_regime_recut_output.txt": "pre-runner tee output\n",
    "dataset.csv": "date,ticker\n2024-06-17,AAPL\n",
}


def _names(paths) -> set[str]:
    return {p.name for p in paths}


def test_keep_latest_keeps_only_the_latest_copies(tmp_path):
    out = _mkdir(tmp_path, _FILES)

    keep, pinned, delete, skipped = classify(out, keep_latest=True, force=False,
                                             citations={})

    assert _names(keep) == {"bear_arm-latest.txt", "book-latest.txt"}
    assert pinned == []
    assert skipped == []
    # Stamped runs AND every non-conforming name are candidates.
    assert _names(delete) == {
        "bear_arm-20260811-185851.txt", "bear_arm-20260812-112717.txt",
        "book-20260811-185757.txt", "bear_arm.txt", "run.txt",
        "mech_regime_recut_output.txt", "dataset.csv",
    }


def test_all_mode_targets_the_latest_copies_too(tmp_path):
    out = _mkdir(tmp_path, _FILES)

    keep, _, delete, _ = classify(out, keep_latest=False, force=False, citations={})

    assert keep == []
    assert _names(delete) == set(_FILES)


def test_cited_file_is_pinned_with_its_citation(tmp_path):
    out = _mkdir(tmp_path, _FILES)
    tuning = tmp_path / "research"
    tuning.mkdir()
    (tuning / "current.md").write_text(
        "Some conclusion.\n\n"
        "**Provenance.** `backtests/study_output/bear_arm-20260811-185851.txt`,\n"
        "git 470b95f.\n")

    citations = cited_files(tuning)
    assert list(citations) == ["bear_arm-20260811-185851.txt"]
    assert citations["bear_arm-20260811-185851.txt"].where == "current.md:3"

    _, pinned, delete, _ = classify(out, keep_latest=True, force=False,
                                    citations=citations)

    assert [(p.name, why) for p, why in pinned] == [
        ("bear_arm-20260811-185851.txt", "cited current.md:3")]
    assert "bear_arm-20260811-185851.txt" not in _names(delete)


def test_gate_marker_pins_the_report_that_carries_it(tmp_path):
    # Mirrors the real hazard: only a stamped calendar_hedge report carries the
    # H2 verdict that calendar_hedge.py's ARM S gate looks for; -latest.txt does
    # not, so a naive keep-latest would revoke the gate.
    out = _mkdir(tmp_path, {
        "calendar_hedge-20260813-130412.txt": "...\nH2 (primary)  verdict: PASS\n",
        "calendar_hedge-20260813-143447.txt": "...\ngates-only run, no verdict\n",
        "calendar_hedge-latest.txt": "...\ngates-only run, no verdict\n",
    })

    keep, pinned, delete, _ = classify(out, keep_latest=True, force=False,
                                       citations={})

    assert _names(keep) == {"calendar_hedge-latest.txt"}
    assert [(p.name, why) for p, why in pinned] == [
        ("calendar_hedge-20260813-130412.txt", 'gate marker "H2 (primary)"')]
    assert _names(delete) == {"calendar_hedge-20260813-143447.txt"}


def test_gate_marker_scan_ignores_non_txt_files(tmp_path):
    out = _mkdir(tmp_path, {"dataset.csv": "note,H2 (primary)\n"})

    _, pinned, delete, _ = classify(out, keep_latest=True, force=False, citations={})

    assert pinned == []
    assert _names(delete) == {"dataset.csv"}


def test_force_deletes_both_pin_classes(tmp_path):
    out = _mkdir(tmp_path, {
        "bear_arm-20260811-185851.txt": "cited run\n",
        "calendar_hedge-20260813-130412.txt": "H2 (primary)  verdict: PASS\n",
    })
    citations = {"bear_arm-20260811-185851.txt": "current.md:3"}

    _, pinned, delete, _ = classify(out, keep_latest=True, force=True,
                                    citations=citations)

    assert pinned == []
    assert len(delete) == 2


def test_pipeline_latest_artifacts_survive_keep_latest(tmp_path):
    # New pipeline artifacts beyond the runner's -latest.txt: study/review steps
    # write -latest.csv and -latest.md copies that must be treated the same way.
    out = _mkdir(tmp_path, {
        "bear_arm-positions-latest.csv": "ticker,qty\n",
        "bear_arm-digest-latest.md": "digest\n",
        "bear_arm-review-analyst-a-latest.md": "review a\n",
        "bear_arm-review-analyst-b-latest.md": "review b\n",
        "bear_arm-review-validator-latest.md": "verdict\n",
        "account_sim-old-notes.md": "stray notes\n",
    })

    keep, pinned, delete, _ = classify(out, keep_latest=True, force=False,
                                       citations={})

    assert _names(keep) == {
        "bear_arm-positions-latest.csv", "bear_arm-digest-latest.md",
        "bear_arm-review-analyst-a-latest.md",
        "bear_arm-review-analyst-b-latest.md",
        "bear_arm-review-validator-latest.md",
    }
    assert pinned == []
    assert _names(delete) == {"account_sim-old-notes.md"}


def test_citation_in_a_nested_archive_dir_is_found(tmp_path):
    # research/archive/ and research/pre-registrations/ hold most of the repo's
    # **Provenance.** lines. A non-recursive glob read none of them, so every
    # archive citation pinned nothing while looking like it did.
    tuning = tmp_path / "research"
    (tuning / "archive").mkdir(parents=True)
    (tuning / "archive" / "13-account-sim.md").write_text(
        "**Provenance.** `backtests/study_output/calendar_hedge-20260813-130412.txt`\n")

    citations = cited_files(tuning)

    assert list(citations) == ["calendar_hedge-20260813-130412.txt"]
    assert citations["calendar_hedge-20260813-130412.txt"].where == (
        "archive/13-account-sim.md:1")


def test_paths_inside_a_fenced_block_are_not_citations(tmp_path):
    # A folded report is quoted verbatim, and study reports print their own
    # export paths. Treating those as citations would pin the very files the
    # fold exists to replace.
    tuning = tmp_path / "research"
    tuning.mkdir()
    (tuning / "current.md").write_text(
        "**Provenance.** `backtests/study_output/account_sim-latest.txt`\n"
        "\n"
        "```text\n"
        "  positions CSV: 447 rows -> backtests/study_output/account_sim-positions-latest.csv\n"
        "```\n")

    assert list(cited_files(tuning)) == ["account_sim-latest.txt"]


def test_code_input_is_pinned_without_any_citation(tmp_path):
    out = _mkdir(tmp_path, {"account_sim-latest.txt": "report\n",
                            "account_sim-positions-latest.csv": "a,b\n",
                            "other-latest.txt": "report\n"})

    _, pinned, delete, _ = classify(out, keep_latest=False, force=False,
                                    citations={})

    assert {p.name for p, _ in pinned} == {"account_sim-latest.txt",
                                           "account_sim-positions-latest.csv"}
    assert all(why.startswith("code input") for _, why in pinned)
    assert _names(delete) == {"other-latest.txt"}


def test_stale_pin_is_flagged_when_the_report_is_not_the_cited_run(tmp_path):
    # The failure this exists for: a cited -latest.txt overwritten by a later
    # run against different exports. The pin held the name; the evidence left.
    out = _mkdir(tmp_path, {
        "bear_arm-latest.txt": _report("bear_arm", "6e4f404", "2026-08-15 19:11:09")})
    doc = tmp_path / "deployment-evidence.md"
    doc.write_text("Evidence (`bear_arm` study, git 470b95f,\n"
                   "`backtests/study_output/bear_arm-latest.txt`): CI [+0.015, +0.065].\n")
    citations = {"bear_arm-latest.txt": Citation("deployment-evidence.md:2", doc, 2)}

    _, pinned, _, _ = classify(out, keep_latest=False, force=False,
                               citations=citations)

    (_, why), = pinned
    assert "STALE" in why and "6e4f404" in why and "470b95f" in why


def test_matching_sha_is_not_flagged_stale(tmp_path):
    out = _mkdir(tmp_path, {
        "bear_arm-latest.txt": _report("bear_arm", "470b95f", "2026-08-11 18:58:51")})
    doc = tmp_path / "deployment-evidence.md"
    doc.write_text("Evidence (`bear_arm` study, git 470b95f,\n"
                   "`backtests/study_output/bear_arm-latest.txt`).\n")
    citations = {"bear_arm-latest.txt": Citation("deployment-evidence.md:2", doc, 2)}

    _, pinned, _, _ = classify(out, keep_latest=False, force=False,
                               citations=citations)

    (_, why), = pinned
    assert why == "cited deployment-evidence.md:2"


def test_citation_claiming_neither_sha_nor_date_is_never_stale(tmp_path):
    # No checkable claim means no contradiction — guessing from prose would
    # flag correct citations.
    out = _mkdir(tmp_path, {
        "bear_arm-latest.txt": _report("bear_arm", "6e4f404", "2026-08-15 19:11:09")})
    doc = tmp_path / "notes.md"
    doc.write_text("See `backtests/study_output/bear_arm-latest.txt` for the run.\n")
    citations = {"bear_arm-latest.txt": Citation("notes.md:1", doc, 1)}

    _, pinned, _, _ = classify(out, keep_latest=False, force=False,
                               citations=citations)

    (_, why), = pinned
    assert why == "cited notes.md:1"


def test_headerless_debris_does_not_raise_the_stale_check(tmp_path):
    # Pre-runner tee output has no provenance header at all. That is not an
    # error; it means there is nothing to check the citation against.
    out = _mkdir(tmp_path, {"bear_arm.txt": "pre-runner tee output\n"})
    doc = tmp_path / "notes.md"
    doc.write_text("`backtests/study_output/bear_arm.txt`, git 470b95f, 2026-08-11.\n")
    citations = {"bear_arm.txt": Citation("notes.md:1", doc, 1)}

    _, pinned, _, _ = classify(out, keep_latest=False, force=False,
                               citations=citations)

    (_, why), = pinned
    assert why == "cited notes.md:1"


def test_subdirectories_are_skipped_not_deleted(tmp_path):
    out = _mkdir(tmp_path, {"run.txt": "x\n"})
    (out / "archive").mkdir()

    _, _, delete, skipped = classify(out, keep_latest=False, force=False,
                                     citations={})

    assert _names(skipped) == {"archive"}
    assert _names(delete) == {"run.txt"}
