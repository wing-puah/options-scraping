"""Tests for scripts/check_doc_links.py — the doc cross-link checker.

Covers slugify() in isolation, the link-checking logic against small
synthetic fixtures under tmp_path, and a real scan of the repo's tracked
docs (docs/ + research/ + the root .md files).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from check_doc_links import ROOT, check, slugify


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"


def test_slugify_backticks_and_em_dash():
    heading = (
        "`bear_arm` — [`pre-registrations/x.md`](pre-registrations/x.md), "
        "`f1_selection/bear_arm.py`"
    )
    slug = slugify(heading)
    # backticks, brackets, parens, dots and slashes are all stripped; the
    # em dash and the punctuation around it collapse to nothing (not a
    # letter/digit/space/hyphen/underscore); underscores inside identifiers
    # survive because the algorithm only strips '*' emphasis, not '_'.
    assert slug == "bear_arm--pre-registrationsxmd-f1_selectionbear_armpy"
    assert "`" not in slug and "[" not in slug and "(" not in slug


def test_slugify_numbered_veto_heading():
    heading = "1. VETO — never deploy, regardless of score"
    assert slugify(heading) == "1-veto--never-deploy-regardless-of-score"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_check_against_synthetic_fixtures(tmp_path):
    root = tmp_path
    good = root / "good.md"
    _write(
        good,
        "# Some Heading\n\n"
        "<a id=\"explicit-anchor\"></a>\n\n"
        "## Some Heading\n",
    )
    main = root / "main.md"
    _write(
        main,
        "# Main\n\n"
        "A good file link: [good](good.md).\n\n"
        "A good anchor link: [good](good.md#some-heading).\n\n"
        "An explicit anchor link: [good](good.md#explicit-anchor).\n\n"
        "A bad file link: [missing](nope.md).\n\n"
        "A bad anchor link: [good](good.md#does-not-exist).\n\n"
        "```\n"
        "a fenced code block link that must be ignored: [x](also-missing.md)\n"
        "```\n\n"
        "An inline code span link that must be ignored: "
        "`[x](also-missing.md)`\n",
    )

    problems = check([main, good], root=root)
    by_target = {p.target: p for p in problems}

    assert "nope.md" in by_target
    assert "good.md#does-not-exist" in by_target
    assert "also-missing.md" not in by_target
    assert "good.md" not in by_target
    assert "good.md#some-heading" not in by_target
    assert "good.md#explicit-anchor" not in by_target
    assert len(problems) == 2


def test_check_site_link_is_warning_not_error(tmp_path):
    root = tmp_path
    (root / "site").mkdir()
    main = root / "main.md"
    _write(main, "[chart](site/chart.html)\n")

    problems = check([main], root=root)
    assert len(problems) == 1
    assert problems[0].warning is True


# ── real repo scan ──────────────────────────────────────────────────────────

_real_problems = check(root=ROOT)
_real_errors = [p.format(ROOT) for p in _real_problems if not p.warning]

if _real_errors:
    print("\nBroken doc links found in the repo:")
    for line in _real_errors:
        print(f"  {line}")


def test_real_repo_has_no_broken_doc_links():
    assert _real_errors == [], "\n".join(_real_errors)
