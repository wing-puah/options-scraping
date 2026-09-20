"""Tests for scripts/check_prose.py — the readability check for research prose.

Covers each rule against a small synthetic fixture, the touched-lines scoping
that lets the check run on files that predate it, the hook's exit-code
contract, and one real file: the writing guide must pass its own check.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from check_prose import ROOT, check_file, check_text, in_scope, run_hook

_LONG = " ".join(["word"] * 60)


def _rules(text: str) -> list[str]:
    return [p.rule for p in check_text(text, Path("x.md")) if not p.warning]


def test_short_entry_is_clean():
    text = "## 2026-09-20 — a study — nothing ships\n\nNo cell beats the plain spread. Nothing ships.\n"
    assert _rules(text) == []


def test_long_table_cell_is_flagged_on_its_own_line():
    text = f"| Item | Fix |\n|---|---|\n| short | {_LONG}. |\n"
    problems = [p for p in check_text(text, Path("x.md")) if p.rule == "cell-too-long"]
    assert [p.line for p in problems] == [3]


def test_table_rule_row_and_fenced_code_are_ignored():
    assert _rules(f"|---|---|\n\n```\n{_LONG} {_LONG} {_LONG}\n```\n") == []


def test_long_sentence_is_flagged_and_short_ones_are_not():
    assert "sentence-too-long" in _rules(f"The {_LONG} ends here.\n")
    assert _rules("One claim. Then another, because the first caused it.\n") == []


def test_long_paragraph_of_short_sentences_is_flagged():
    text = " ".join(["This is a short sentence."] * 30) + "\n"
    assert _rules(text) == ["paragraph-too-long"]


def test_list_items_are_separate_blocks():
    item = " ".join(["This is a short sentence."] * 12)
    assert _rules(f"- {item}\n- {item}\n- {item}\n") == []


def test_figures_rule_ignores_dates_section_refs_links_and_code():
    clean = "On 2026-09-08 the run in [§2.11](next-steps.md#s2-11) used `top_k=3` and moved 14 rows.\n"
    assert _rules(clean) == []
    dense = "It moved 14 of 598 rows, 8 of 57 proxy rows, and the mean went from +0.277 to +0.251.\n"
    assert _rules(dense) == ["too-many-figures"]


def test_figures_inside_a_table_are_fine():
    assert _rules("| 14 | 598 | 8 | 57 | +0.277 | +0.251 |\n") == []


def test_shouting_flags_ordinary_words_but_not_tokens_or_tickers():
    assert _rules("The study printed UNDERPOWERED on SPY and NULL on IWM, and TLT was CONTRARY.\n") == []
    assert _rules("This is NOT a gate and it must NEVER be read as one.\n") == ["shouting"]


def test_long_heading_is_flagged():
    assert _rules("## 2026-09-20 — " + "a heading that says far too much " * 4 + "\n") == ["heading-too-long"]


def test_vague_word_is_advisory_only():
    problems = check_text("The posture is unchanged.\n", Path("x.md"))
    assert [p.warning for p in problems] == [True]


@pytest.mark.parametrize(
    "rel, expected",
    [
        ("research/current.md", True),
        ("docs/architecture.md", True),
        ("research/archive/19-x.md", False),
        ("research/study-results/f1_selection/x.md", False),
        ("research/pre-registrations/f1_selection/x.md", False),
        ("scripts/journal/README.md", False),
        ("research/notes.txt", False),
    ],
)
def test_scope(rel, expected):
    assert in_scope(ROOT / rel) is expected


def test_only_touched_blocks_are_reported(tmp_path):
    path = tmp_path / "f.md"
    path.write_text(f"Legacy {_LONG} legacy.\n\nNew and short.\n", encoding="utf-8")
    assert check_file(path, [(3, 3)]) == []
    assert [p.line for p in check_file(path, [(1, 1)])] == [1]


def _hook(tmp_path, monkeypatch, body: str, new_string: str | None):
    """Run the hook against a fake repo root holding research/f.md."""
    path = tmp_path / "research" / "f.md"
    path.parent.mkdir()
    path.write_text(body, encoding="utf-8")
    tool_input = {"file_path": str(path)}
    if new_string is not None:
        tool_input["new_string"] = new_string
    return run_hook(json.dumps({"tool_name": "Edit", "tool_input": tool_input}), root=tmp_path)


def test_hook_blocks_on_the_edited_block_only(tmp_path, monkeypatch, capsys):
    body = f"Legacy {_LONG} legacy.\n\nNew and short.\n"
    assert _hook(tmp_path, monkeypatch, body, "New and short.") == 0
    assert capsys.readouterr().err == ""


def test_hook_exits_2_and_names_the_line(tmp_path, monkeypatch, capsys):
    new = f"Added {_LONG} today."
    assert _hook(tmp_path, monkeypatch, f"Fine.\n\n{new}\n", new) == 2
    err = capsys.readouterr().err
    assert "research/f.md:3: sentence-too-long" in err
    assert "keeping every fact" in err


def test_hook_checks_the_whole_file_on_a_write(tmp_path, monkeypatch):
    assert _hook(tmp_path, monkeypatch, f"Legacy {_LONG} legacy.\n", None) == 2


def test_hook_never_fails_a_tool_call(tmp_path):
    assert run_hook("not json") == 0
    assert run_hook(json.dumps({"tool_input": {"file_path": str(tmp_path / "missing.md")}})) == 0
    assert run_hook(json.dumps({"tool_input": {"file_path": str(ROOT / "scripts" / "check_prose.py")}})) == 0


def test_the_writing_guide_passes_its_own_check():
    problems = [p for p in check_file(ROOT / "research" / "writing-guide.md") if not p.warning]
    assert problems == []
