"""`research/arm-index.md` claims to index EVERY label in this repo that reads
like an arm, so test it.

An arm label is study-local: `ARM P` is emission persistence in
`emission_timing`, P&L outcomes in `macro_event_study`, the `be_after`
production baseline in `bear_giveback`, and portfolio contribution in
`bear_rewrap`. That is fine — arms belong to their study — but it makes a bare
`grep "ARM P"` useless as a lookup: it returns ~200 hits, most of them one
study CITING another's arm. The index exists so the answer is one search, and
it is only worth having if it cannot go stale.

So: every `ARM <label>` token appearing in a live study module or in a
pre-registration must have a mention in the index. Registering a new arm
without indexing it fails here.

The index also carries the labels that are NOT arms — `G*` gates, `H0`-`H5`
criteria, `H1`-`H4` hypotheses, `account_sim`'s CLI arms, report prose — each
tagged with a kind in parentheses. Those CANNOT be tested for coverage: no
token shape identifies a gate, so nothing here distinguishes "not indexed"
from "does not exist". They are hand-maintained.

What this does NOT check:

  * the DESCRIPTIONS. Like `study_map/catalog.py`'s verdicts, they are the
    operator's own words and no test should assert prose.
  * `research/current.md`, `archive/`, or `study-results/`. Those are the
    historical record and quote arms as they printed, including retired ones;
    demanding an index mention for every arm ever cited would make the index
    a changelog rather than a lookup.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "research" / "arm-index.md"
STUDY_PKG = ROOT / "scripts" / "backtest_study"
PREREGS = ROOT / "research" / "pre-registrations"

# `ARM P`, `ARM CK`, `ARM H*`, `ARM V-price`, `ARM D0`, `ARM VERDICT`.
ARM_TOKEN = re.compile(r"\bARM ([A-Z][A-Za-z0-9*-]*)")

# Every backticked token in the index, which is how a label is written there.
BACKTICKED = re.compile(r"`([^`]+)`")

# A study's own section: `#### `study_name` — <where defined>`.
_STUDY_HEADING = re.compile(r"^#### `([a-z][a-z0-9_]*)`", re.M)


def _sources() -> list[Path]:
    return sorted(STUDY_PKG.rglob("*.py")) + sorted(PREREGS.glob("*.md"))


def _study_sections(text: str) -> list[tuple[str, str]]:
    """Split the index's "by study" body into (study_name, section_text)
    pairs, each running up to the next level-4-or-higher heading."""
    headings = list(_STUDY_HEADING.finditer(text))
    sections = []
    for i, m in enumerate(headings):
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        sections.append((m.group(1), text[start:end]))
    return sections


def _indexed_labels() -> set[str]:
    # Fenced blocks first: ``` is an ODD run of backticks, so leaving a usage
    # example in shifts every inline-code pair after it by one and the whole
    # extraction silently reads punctuation as labels.
    text = re.sub(r"```.*?```", "", INDEX.read_text(encoding="utf-8"), flags=re.S)
    labels: set[str] = set()
    for token in BACKTICKED.findall(text):
        token = token.strip()
        labels.add(token)
        if token.startswith("ARM "):
            labels.add(token[4:].strip())
    return labels


def test_index_exists_and_is_readable() -> None:
    assert INDEX.is_file(), f"{INDEX} is the arm lookup readers are pointed at; it must exist"


@pytest.mark.parametrize("source", _sources(), ids=lambda p: p.name)
def test_every_arm_label_is_indexed(source: Path) -> None:
    indexed = _indexed_labels()
    found = set(ARM_TOKEN.findall(source.read_text(encoding="utf-8")))
    missing = sorted(label for label in found if label not in indexed)
    assert not missing, (
        f"{source.relative_to(ROOT)} uses arm label(s) {missing} with no mention in "
        f"research/arm-index.md. Add it under its study's heading in "
        f"research/arm-index.md (label, kind, what it varies, where defined)."
    )


def test_index_covers_the_known_collisions() -> None:
    """The four `ARM P` owners are the reason this file exists — pin them."""
    text = INDEX.read_text(encoding="utf-8")
    owners = {
        study
        for study, section in _study_sections(text)
        if re.search(r"(?m)^- `ARM P`", section)
    }
    assert owners == {
        "emission_timing",
        "macro_event_study",
        "bear_giveback",
        "bear_rewrap",
    }, f"ARM P owners drifted: {sorted(owners)}"
