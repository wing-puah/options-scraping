"""Which prompt-version ERA an export belongs to, and where that era's files live.

THE SINGLE ENCODING of "what population is this study running on". Every study
resolves its input paths and checks its era through this module; a second copy
of either rule would let two studies disagree about what book they read.

--- Why this module exists --------------------------------------------------
A prompt-version bump renames the LIVE Sheets tabs in place (`AnalysisClaude`
-> `v3_AnalysisClaude`) and lets the pipeline recreate empty ones. The exported
CSV keeps the tab's name, so the BARE filename
`backtests/to_evaluate/analysis - AnalysisClaude.csv` does not name a fixed
population: it names *whatever the live tab held at export time*.

On 2026-08-15 that bit. The bare exports were refreshed at 19:01, four months
of v3 evidence silently became 14 dates of v4, and every study that read the
bare name changed population without changing a line of code. Five studies
failed loudly on calibration gates; FOURTEEN succeeded quietly and promoted
`-latest.txt` reports whose numbers no longer matched the verdicts written
against them. Those reports are unrecoverable — `backtests/*` is gitignored.

`research/archive/09-v3-closeout.md` recorded the assumption that broke:
"Study code is unaffected — it reads CSV exports by filename, not tabs."
It reads exports by filename, and the filename changed meaning.

The fix is not to pin studies to a frozen snapshot — a study that can only run
on a dead export has stopped being research. It is to make the era EXPLICIT and
CHECKED, so a re-export can never change what a study reads without the study
saying so in its own report.

--- Detection ---------------------------------------------------------------
`score_flow` / `score_dealer` were DROPPED at the v4 bump and are not coming
back, which makes them a durable discriminator rather than a passing tell.

They are not, however, absent from every v4 export. `RESULT_COLUMNS`
(`scripts/backtest/core.py`) deliberately KEEPS both columns so that loaders
work across pooled exports, so `BacktestResults` / `BacktestProxy` carry the
column in both eras and only the VALUES separate them:

    analysis - v3_AnalysisClaude.csv     column present    1465/1607 non-blank
    analysis - AnalysisClaude.csv        column ABSENT     -> v4
    analysis - v3_BacktestResults.csv    column present     406/406  non-blank
    analysis - BacktestResults.csv       column present       0/30   non-blank

So the rule is `present AND at least one non-blank value`, which is correct for
both shapes. Testing presence alone — as `v4_bridge.detect_era` did before this
module absorbed it — reads every v4 results export as v3.

LIMIT, stated plainly: this discriminates v3 from NOT-v3. A future v5 would
also lack populated `score_flow` and would be reported here as "v4". Add the v5
discriminator to `_ERA_TESTS` at that bump; do not let a v5 export quietly
answer to "v4".
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "backtests" / "to_evaluate"

# The three exports whose identity decides which population a study ran on.
EXPORTS: dict[str, str] = {
    "results": "BacktestResults",
    "proxy": "BacktestProxy",
    "analysis": "AnalysisClaude",
}

# Populated on v3, dropped at the v4 bump and not returning. See module
# docstring: presence alone is NOT the test.
V3_ONLY_COLS = ("score_flow", "score_dealer")

# The default era. "current" resolves to the BARE filenames — whatever the live
# tabs hold now. Deliberately not a hardcoded "v4": a version bump should not
# require editing a constant here, and `detect_era` reports what it actually is.
CURRENT = "current"

# A study needs this many distinct signal dates before it is allowed to
# conclude anything. A POWER floor, not a snapshot fingerprint: it is satisfied
# permanently once an era reaches it, where a stored figure like
# "expected_positions: 220" breaks on every legitimate data refresh.
#
# 30 is `ml_combination.MIN_TRAIN_DATES` — the smallest date count at which the
# purged walk-forward can emit a single block. Below it, that study produced an
# IndexError rather than a diagnosis.
MIN_ERA_DATES = 30

# Designed refusals, in the sense `run.py` means it: a non-zero exit that is the
# study's CORRECT current status, not a failure. A study using them must declare
# `DESIGNED_REFUSAL_EXIT_CODES` at module level — run.py finds it by AST parse,
# so it has to be a literal module-level assignment, not an import alias.
EXIT_THIN_ERA = 2       # era too small to conclude from
EXIT_ERA_MISMATCH = 3   # the export on disk is not the era that was asked for
DESIGNED_REFUSAL_EXIT_CODES = frozenset({EXIT_THIN_ERA, EXIT_ERA_MISMATCH})


def requested_era() -> str:
    """The era this process was asked for: `STUDY_ERA`, else `current`.

    An env var rather than a per-study `--era` flag on purpose. The runner sets
    it once for the whole suite; threading a flag through fourteen argparse
    blocks would be a far larger change that buys nothing a study actually uses.
    """
    return os.environ.get("STUDY_ERA", "").strip() or CURRENT


def prefix_for(era: str) -> str:
    """Filename prefix for `era`. `current` is the bare (unprefixed) export."""
    return "" if era == CURRENT else f"{era}_"


def resolve_paths(era: str | None = None) -> dict[str, Path]:
    """`{"results": Path, "proxy": Path, "analysis": Path}` for `era`."""
    era = era or requested_era()
    pre = prefix_for(era)
    return {key: EVAL_DIR / f"analysis - {pre}{tab}.csv" for key, tab in EXPORTS.items()}


def detect_era(path: Path) -> str:
    """`"v3"` or `"v4"` for the export at `path`, by the rule in the docstring.

    Streams and short-circuits on the first non-blank `score_flow`, so this
    stays cheap on the 11k-row analysis export.

    Raises `ValueError` on an export with no data rows: era is genuinely
    indeterminate there, and guessing "v4" would let an empty or truncated v3
    export pass an era check it should fail.
    """
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        cols = reader.fieldnames or []
        present = [c for c in V3_ONLY_COLS if c in cols]
        n_rows = 0
        for row in reader:
            n_rows += 1
            if any(str(row.get(c) or "").strip() for c in present):
                return "v3"
        if n_rows == 0:
            raise ValueError(
                f"{path.name}: no data rows — era is indeterminate. An empty or "
                f"truncated export must not be read as v4 by default."
            )
    return "v4"


def enforce(era: str, paths: dict[str, Path]) -> str:
    """Check every export in `paths` really is `era`; refuse if not.

    Refuses on TWO conditions, both of which mean a study is about to attribute
    numbers to the wrong population:
      - an export whose detected era is not the one requested, and
      - exports that disagree with EACH OTHER, which is a half-finished
        re-export and is worse than either era alone.

    Returns the detected era (identical to `era` unless `era` is `current`, in
    which case this resolves what `current` currently means).
    """
    detected: dict[str, str] = {}
    for key, path in paths.items():
        if not path.exists():
            continue
        try:
            detected[key] = detect_era(path)
        except ValueError as exc:
            _refuse(EXIT_ERA_MISMATCH, str(exc))

    if not detected:
        listed = "\n".join(f"    {p}" for p in paths.values())
        _refuse(EXIT_ERA_MISMATCH,
                f"no exports found for era {era!r} — looked for:\n{listed}")

    distinct = set(detected.values())
    if len(distinct) > 1:
        lines = "\n".join(f"    {detected[k]:<3} {paths[k].name}"
                          for k in sorted(detected))
        _refuse(EXIT_ERA_MISMATCH,
                f"the exports disagree about their era — a half-finished "
                f"re-export:\n{lines}\n"
                f"  Re-export all three from the same set of tabs.")

    actual = distinct.pop()
    if era != CURRENT and actual != era:
        lines = "\n".join(f"    {paths[k].name}" for k in sorted(detected))
        _refuse(EXIT_ERA_MISMATCH,
                f"asked for era {era!r}, but these exports are {actual!r}:\n{lines}")
    return actual


def require_dates(n_dates: int, era: str, minimum: int = MIN_ERA_DATES,
                  what: str = "") -> None:
    """Refuse, with the numbers, when `era` is too thin to conclude from.

    This is the honest output of a study on a young era — not a crash, and not
    an underpowered figure that gets quoted into the study map and read as a
    finding. `run.py` promotes a designed refusal to `-latest.txt`, so the
    current report says exactly this rather than silently keeping older numbers.
    """
    if n_dates >= minimum:
        return
    detail = f" ({what})" if what else ""
    _refuse(EXIT_THIN_ERA,
            f"era {era} has {n_dates} dates; this study needs "
            f"{minimum}{detail}.\n"
            f"  {minimum - n_dates} more to go. Not a failure, and not a "
            f"reason to lower the floor — re-run as the era accrues.")


def _refuse(code: int, message: str) -> None:
    print(f"\nREFUSED — {message}")
    sys.exit(code)
