from pathlib import Path

from clean_study_output import cited_files, classify


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
    assert citations == {"bear_arm-20260811-185851.txt": "current.md:3"}

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


def test_subdirectories_are_skipped_not_deleted(tmp_path):
    out = _mkdir(tmp_path, {"run.txt": "x\n"})
    (out / "archive").mkdir()

    _, _, delete, skipped = classify(out, keep_latest=False, force=False,
                                     citations={})

    assert _names(skipped) == {"archive"}
    assert _names(delete) == {"run.txt"}
