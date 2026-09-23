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

The index also guarantees every label bullet is tagged with an object type
from a closed list (arm, sub-arm, cell, control, descriptive cut, population
scope, run, gate, criterion, hypothesis, prose, axis) — so "arm" stops being
the universal noun for anything that carries a study-local letter. Adding a
new object type means editing the table at `research/arm-index.md#object-types`
AND the `OBJECT_TYPES` set below; the two must never drift apart.
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

# A label bullet, at any indent: `- `ARM U` ...` or `  - `ARM U/a` ...`.
_LABEL_BULLET_LINE = re.compile(r"^\s*- `", re.M)

# The parenthesised object-type tag right after a label bullet's backticked
# label(s), before the ` — `: `- `ARM U` (sub-arm) — ...`.
_LABEL_BULLET_TAG = re.compile(r"^\s*- (?:`[^`]+`\s*)+\(([a-z][a-z -]*)\)")

# The closed vocabulary of object types a label bullet may be tagged with.
# Keep in sync with the table under `## Object types` in arm-index.md.
OBJECT_TYPES = {
    "arm",
    "sub-arm",
    "cell",
    "control",
    "descriptive cut",
    "population scope",
    "run",
    "gate",
    "criterion",
    "hypothesis",
    "prose",
    "axis",
}


def _sources() -> list[Path]:
    preregs = sorted(p for p in PREREGS.rglob("*.md") if p.name != "README.md")
    return sorted(STUDY_PKG.rglob("*.py")) + preregs


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


# `ARM <TICKER>` false positives: a sector-map ticker list writes tickers
# space-separated with no punctuation, so when the ARM Holdings ticker
# ("ARM") is immediately followed by another ticker, ARM_TOKEN reads the two
# as one arm citation. These are prose in an IMMUTABLE registration (fixed
# 2026-08-29, per its own "sector map is fixed HERE" clause) — not a study
# arm — so they cannot be indexed and are not a coverage gap. Pinned here,
# by file and label, the same way test_index_covers_the_known_collisions
# pins the ARM P owners: a new entry needs a comment naming the ticker list
# it comes from, never a silent addition.
_KNOWN_TICKER_FALSE_POSITIVES: dict[str, set[str]] = {
    "hedge_portfolio.md": {"MRVL"},  # `SEMIS` sector map: "... AMAT ARM MRVL INTC ..."
}


def test_index_exists_and_is_readable() -> None:
    assert INDEX.is_file(), f"{INDEX} is the arm lookup readers are pointed at; it must exist"


@pytest.mark.parametrize("source", _sources(), ids=lambda p: p.name)
def test_every_arm_label_is_indexed(source: Path) -> None:
    indexed = _indexed_labels()
    found = set(ARM_TOKEN.findall(source.read_text(encoding="utf-8")))
    found -= _KNOWN_TICKER_FALSE_POSITIVES.get(source.name, set())
    missing = sorted(label for label in found if label not in indexed)
    assert not missing, (
        f"{source.relative_to(ROOT)} uses arm label(s) {missing} with no mention in "
        f"research/arm-index.md. Add it under its study's heading in "
        f"research/arm-index.md (label, kind, what it varies, where defined)."
    )


def test_index_covers_the_known_collisions() -> None:
    """The `ARM P` owners are the reason this file exists — pin them.

    Six now: `hedge_portfolio` registered its own `ARM P` (the prose-free
    counterpart to `ARM CS`) on 2026-08-29, and `exit_drawdown` registered
    partial scale-out as its `ARM P` on 2026-09-05. The pin is updated when a
    study genuinely claims the label, never to make a collision go quiet.
    """
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
        "hedge_portfolio",
        "exit_drawdown",
    }, f"ARM P owners drifted: {sorted(owners)}"


def test_every_label_bullet_carries_a_known_object_type() -> None:
    """Every label bullet in the index must carry a parenthesised
    object-type tag, right after the label and before the ` — `.

    Only the body from the first `#### ` study heading onward is checked —
    the card's own table and the "Collisions, up front" list above it are
    not label bullets in the index's own sense.
    """
    text = re.sub(r"```.*?```", "", INDEX.read_text(encoding="utf-8"), flags=re.S)
    first_heading = re.search(r"^#### ", text, re.M)
    assert first_heading is not None, f"{INDEX} has no `#### ` study heading to start from"
    body = text[first_heading.start():]

    offenders = []
    for lineno, line in enumerate(body.splitlines(), start=1):
        if not _LABEL_BULLET_LINE.match(line):
            continue
        tag_match = _LABEL_BULLET_TAG.match(line)
        if tag_match is None:
            offenders.append(f"line {lineno}: no object-type tag -- {line.strip()!r}")
            continue
        tag = tag_match.group(1)
        if tag not in OBJECT_TYPES:
            offenders.append(f"line {lineno}: unknown object type {tag!r} -- {line.strip()!r}")

    assert not offenders, (
        "research/arm-index.md has label bullet(s) with a missing or unknown "
        f"object-type tag. Every label bullet must be tagged `(<object type>)` "
        f"from {sorted(OBJECT_TYPES)} right after the label, before the "
        "` — `:\n" + "\n".join(offenders)
    )
