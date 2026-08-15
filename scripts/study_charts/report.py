"""Parse an `account_sim` text report into a dict the renderer can draw.

The report is a fixed-width artifact written for a human reader, so this parser
is deliberately strict: every section it wants is looked up by its exact banner
title, and a missing section raises rather than yielding an empty chart. A study
report that changed shape should break the build loudly — a chart drawn from a
half-parsed report is worse than no chart.

That strictness has one precondition, added 2026-08-16: the thing being parsed
has to BE a report. Studies are era-scoped now, and a study whose era is too
thin to conclude from REFUSES — it prints its refusal, exits with a designed
non-zero code, and `run.py` promotes that to `-latest.txt` because it is the
study's correct current status. Handing that to `parse()` produced a
`ReportParseError` about a missing CONFIGURATION separator: true, useless, and
pointing at the wrong file. `read_refusal()` below is the guard every entry
point runs BEFORE parsing. It does not soften the loud path — a genuinely
malformed report still raises, which is the property the paragraph above is
about; it only stops that error being raised about a file that never claimed to
be a full report.
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import NamedTuple

# What counts as a DESIGNED refusal is the runner's vocabulary, not the chart
# layer's — imported rather than re-listed here so the two cannot disagree. A
# copy of `{2, 3}` in this file would go stale the day a third code is added,
# and "the chart layer and the runner agree about what a refusal is" is the
# entire content of this check.
#
# Two spellings because this module has two entry paths: the chart package is
# imported as `scripts.study_charts.report` (repo ROOT on sys.path), while
# `scripts/clean_study_output.py` runs as a script and gets only `scripts/` on
# sys.path, where the same package is spelled `backtest_study.lib.era`.
try:
    from scripts.backtest_study.lib.era import DESIGNED_REFUSAL_EXIT_CODES
except ImportError:  # running with scripts/ on sys.path, not the repo root
    from backtest_study.lib.era import DESIGNED_REFUSAL_EXIT_CODES

BANNER = "=" * 78
POPULATIONS = {"primary": "PRIMARY dense episodes", "secondary": "SECONDARY full book"}

# The runner's footer, written at the end of EVERY report it captures:
#     ==============...
#     exit code 2 after 1.9s
#     ==============...
# The exit code is the STRUCTURED fact about how a run ended, which is why it —
# and not a grep for "REFUSED" in the body — is what `read_refusal` keys on. The
# refusal WORDING is prose a study is free to reword; the code is declared in
# `era.DESIGNED_REFUSAL_EXIT_CODES` and cannot drift silently.
_EXIT_FOOTER_RE = re.compile(r"^exit code (-?\d+) after [\d.]+s\s*$", re.M)

# The refusal text itself: `era._refuse` prints "\nREFUSED — <message>", where
# the message may run to several indented lines, and the footer banner is the
# next thing in the file. Captured only to QUOTE back to a human — never parsed
# for meaning, so a reworded message costs nothing.
_REFUSAL_RE = re.compile(r"^REFUSED —[ \t]*(.*?)(?=\n=====|\Z)", re.M | re.S)

# What `parse_provenance` reports for a run that recorded no era. Reused by the
# refusal path so an unknown era reads the same everywhere it is printed.
UNKNOWN_ERA = "?"


class ReportParseError(RuntimeError):
    """The report did not contain a section this renderer needs."""


class Refusal(NamedTuple):
    """A study's DESIGNED refusal, read off the report it wrote.

    Not an error: the study ran, decided it had no business concluding
    anything yet, and said so. Callers print it and skip.
    """
    code: int       # the runner's footer exit code, in DESIGNED_REFUSAL_EXIT_CODES
    message: str    # the study's own REFUSED text, verbatim and unparsed
    era: str        # the era that run read, from the provenance header


def _num(text: str) -> float:
    """Parse a report number: strips $ , % x and a leading +."""
    cleaned = re.sub(r"[$,%x]", "", text.strip()).replace("+", "")
    return float(cleaned)


def split_sections(text: str) -> list[tuple[str, list[str]]]:
    """Split the report into (banner title, body lines) pairs, in file order."""
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    i = 0
    while i < len(lines):
        if lines[i].startswith(BANNER) and i + 2 < len(lines) and lines[i + 2].startswith(BANNER):
            title = lines[i + 1].strip()
            body: list[str] = []
            i += 3
            while i < len(lines):
                if lines[i].startswith(BANNER) and i + 2 < len(lines) and lines[i + 2].startswith(BANNER):
                    break
                body.append(lines[i])
                i += 1
            sections.append((title, body))
        else:
            i += 1
    return sections


class Report:
    """Indexed access to a parsed report's sections."""

    def __init__(self, text: str, path: Path):
        self.text = text
        self.path = path
        self.sections = split_sections(text)
        if not self.sections:
            raise ReportParseError(f"{path}: no banner sections found — is this an account_sim report?")

    def body(self, startswith: str) -> list[str]:
        for title, body in self.sections:
            if title.startswith(startswith):
                return body
        raise ReportParseError(f"{self.path}: no section titled {startswith!r}")

    def scoped(self, population: str, startswith: str) -> list[str]:
        return self.body(f"[{POPULATIONS[population]}] {startswith}")

    def find(self, pattern: str, body: list[str], what: str) -> re.Match:
        for line in body:
            m = re.search(pattern, line)
            if m:
                return m
        raise ReportParseError(f"{self.path}: could not find {what}")

    @property
    def exit_code(self) -> int | None:
        """The runner's footer exit code, or None on a report that has no footer.

        LAST match, not first: the footer is the last thing in the file by
        construction, and a study is free to print the phrase in its own body.
        None covers a report captured some other way (a hand-saved excerpt, a
        `tee` from before the runner existed) — those are not refusals and are
        parsed as normal.
        """
        codes = _EXIT_FOOTER_RE.findall(self.text)
        return int(codes[-1]) if codes else None

    @property
    def refusal(self) -> Refusal | None:
        """This report's designed refusal, or None if it is a real report.

        The exit code decides; the message is only quoted. A report that exits
        with a refusal code but prints no REFUSED line still counts as one —
        the code is the declaration, and saying so beats parsing a full report
        out of a run that did not produce one.
        """
        code = self.exit_code
        if code is None or code == 0 or code not in DESIGNED_REFUSAL_EXIT_CODES:
            return None
        found = _REFUSAL_RE.findall(self.text)
        message = found[-1].strip() if found else (
            f"(exit {code}, but the report carries no REFUSED line — "
            f"read {self.path.name} in full)"
        )
        # The provenance header is written by the runner BEFORE the study runs,
        # so a refusal has one. Degrading to UNKNOWN_ERA rather than raising
        # keeps this guard total: its whole job is to answer "is this
        # parseable?", and it must not itself become a way to fail.
        try:
            era = parse_provenance(self)["era"]
        except ReportParseError:
            era = UNKNOWN_ERA
        return Refusal(code=code, message=message, era=era)


# --------------------------------------------------------------------------
# whole-report sections
# --------------------------------------------------------------------------

def read_refusal(path: Path) -> Refusal | None:
    """`Refusal` if the report at `path` is a designed refusal, else None.

    The guard every chart entry point runs before `parse()`. Returns None —
    NOT a refusal — for anything it cannot read as a report at all, so a
    genuinely malformed file falls through to `parse()` and raises there, in
    the loud, specific way this module is built to. Deciding "unparseable"
    here would swallow exactly the failure the strictness exists to catch.
    """
    try:
        return Report(path.read_text(), path).refusal
    except (OSError, ReportParseError):
        return None


def parse_provenance(rep: Report) -> dict:
    body = rep.body("STUDY:")
    out: dict = {"inputs": []}
    for line in body:
        if m := re.match(r"\s+run at\s+(.+)", line):
            out["run_at"] = m.group(1).strip()
        elif m := re.match(r"\s+command\s+(.+)", line):
            out["command"] = m.group(1).strip()
        elif m := re.match(r"\s+git\s+(.+)", line):
            out["git"] = m.group(1).strip()
        elif m := re.match(r"\s+python\s+(.+)", line):
            out["python"] = m.group(1).strip()
        elif m := re.match(r"\s+era\s+(\S+)", line):
            out["era"] = m.group(1).strip()
        elif m := re.match(r"\s+([\d,]+) rows\s+(\S+ \S+)\s+(.+)", line):
            out["inputs"].append(
                {"rows": int(m.group(1).replace(",", "")), "mtime": m.group(2), "path": m.group(3).strip()}
            )
    for key in ("run_at", "command", "git"):
        if key not in out:
            raise ReportParseError(f"{rep.path}: provenance header missing {key!r}")
    # Not required: reports written before the era line existed (2026-08-15)
    # are still parseable, and a caller that cares can test for the default.
    # "?" rather than "current" on purpose — an old report genuinely does not
    # record which era it ran on, and that is exactly the ambiguity that made
    # the era line necessary. Do not let it answer to a real era name.
    out.setdefault("era", UNKNOWN_ERA)
    out["structure_arm"] = "--structure-universe" in out["command"]
    # The second, independent arm axis: the compounding sensitivity re-marks
    # SIZING to realized equity. Derived from the command line for the same
    # reason the structure axis is — the report's own record of how it was run
    # is the only thing that cannot drift from the run that produced it.
    out["compound_arm"] = "--compounding" in out["command"]
    return out


def parse_gates(rep: Report) -> dict:
    """The GATES section's verdicts — G2..G5, four of them.

    FOUR, not five, and the ids start at G2: `account_sim`'s G1 was a
    book-calibration checksum against constants stored in the config, removed
    2026-08-15 because those constants fingerprinted one export and so failed on
    every legitimate data refresh. Its calibration numbers are still printed, in
    a BOOK CALIBRATION section that renders no verdict — this parser
    deliberately does not read them, because a page drawing them next to the
    gate chips would re-imply the pass/fail they no longer carry.

    The surviving gates were NOT renumbered: G2-G5 name specific checks in the
    pre-registration and in every recorded verdict, so sliding them down one
    would silently re-point that prose.
    """
    body = rep.body("GATES —")
    gates = []
    for line in body:
        if m := re.match(r"\s+(G\d): (PASS|FAIL)(.*)", line):
            gates.append({"id": m.group(1), "status": m.group(2), "note": m.group(3).strip()})
    if len(gates) != 4:
        raise ReportParseError(f"{rep.path}: expected 4 gate verdicts (G2-G5), found {len(gates)}")
    headline = rep.find(r"GATES: (.+)", body, "the GATES summary line").group(1).strip()
    titles = {
        "G2": "Scaling identity calibrated at scale=1 against stored rows",
        "G3": "Ledger accounting identity, checked after every event",
        "G4": "Unconstrained walk reproduces top_k_per_day by set equality",
        "G5": "The simulator is blind to how a position turned out",
    }
    for g in gates:
        # Named, not `.get(..., "")`: an id this parser has no title for is a
        # report whose gate set moved, and a chip captioned with a blank is how
        # a renumbering would ship unnoticed.
        if g["id"] not in titles:
            raise ReportParseError(
                f"{rep.path}: unknown gate {g['id']!r} — this parser knows "
                f"{', '.join(sorted(titles))}")
        g["title"] = titles[g["id"]]
    return {"gates": gates, "headline": headline}


def parse_episodes(rep: Report) -> dict:
    body = rep.body("POPULATION —")
    episodes = []
    for line in body:
        if m := re.match(
            r"\s+(E\d)\s+(\d{4}-\d\d-\d\d) \.\. (\d{4}-\d\d-\d\d)\s+(\d+) dates over"
            r"\s+(\d+) sessions\s+(\d+) deployed picks",
            line,
        ):
            episodes.append(
                {
                    "id": m.group(1),
                    "start": m.group(2),
                    "end": m.group(3),
                    "dates": int(m.group(4)),
                    "sessions": int(m.group(5)),
                    "picks": int(m.group(6)),
                }
            )
    if not episodes:
        raise ReportParseError(f"{rep.path}: no episodes parsed from POPULATION —")
    span = rep.find(r"deployed signal dates: (\d+)\s+\((\S+) \.\. (\S+)\)", body, "the deployed signal-date span")
    excluded = rep.find(r"excluded from PRIMARY: (\d+) isolated dates", body, "the excluded-dates line")
    return {
        "episodes": episodes,
        "signal_dates": int(span.group(1)),
        "span": [span.group(2), span.group(3)],
        "excluded_isolated": int(excluded.group(1)),
    }


def parse_verdict(rep: Report) -> dict:
    body = rep.body("VERDICT (")
    checklist = []
    for line in body:
        if m := re.match(r"\s+(A\d)\s+(MET|NOT MET)\s*$", line):
            checklist.append({"id": m.group(1), "status": m.group(2)})
    if not checklist:
        raise ReportParseError(f"{rep.path}: no A1-A6 checklist lines parsed from VERDICT (")
    headline = rep.find(r">>> (.+?) <<<", body, "the verdict headline").group(1).strip()
    return {"checklist": checklist, "headline": headline}


def parse_account_config(rep: Report) -> dict:
    """The `account_sim — $... FEASIBILITY simulation` header block.

    That banner's own title bakes the configured capital into its text
    (`$25,000 FEASIBILITY simulation ...`) AND — because `run.py`'s shared
    `STUDY:` header prints a redundant closing banner ahead of it —
    `split_sections()` folds this whole block into the body of a blank-titled
    phantom section rather than a section of its own (see the `''` entries in
    `Report.sections`). Scoping this lookup through `body()`/`scoped()` would
    depend on that quirk; searching the raw text instead is simpler and does
    not care where the block ends up sectioned. `max_positions_per_day` is
    config-driven (`config/account-sim.yml`), so prose elsewhere reads it back
    from here instead of assuming a fixed count.
    """
    lines = rep.text.splitlines()
    m = rep.find(
        r"(\d+) positions/day, per-position delta-notional cap", lines, "the positions/day line"
    )
    return {"max_per_day": int(m.group(1))}


# The two `sub()` groups the study prints inside CONFIGURATION. The study owns
# the exact titles (`account_sim.CFG_FILE_GROUP` / `CFG_EXITS_GROUP`); this
# parser keys off these markers, and a rename on either side fails the build
# rather than silently swapping which half the page calls "the config file".
CONFIG_FILE_MARKER = "verbatim"
CONFIG_EXITS_MARKER = "exits"

# What the study indents the config file by, so its lines sit in the report's
# body column. Stripped back off here, leaving the file's own bytes.
CONFIG_FILE_INDENT = "  "


def parse_configuration(rep: Report) -> dict:
    """The `CONFIGURATION —` section: the config file the run actually loaded.

    Two groups, and they are read differently on purpose. The FIRST is the
    config file itself, echoed by the run from the same bytes it parsed; it is
    carried through as text with only the report's indent removed, so the page
    shows the file rather than anyone's rendering of it. The SECOND is the
    frozen exit policy, which is not in that file and is printed as
    `  <label>` + 4-or-more spaces + `<value>` rows.

    A missing section raises like every other, so an older report cannot
    silently render a page with an empty setup panel.
    """
    body = rep.body("CONFIGURATION —")
    source = rep.find(r"CONFIGURATION — .*\(([^()]+)\)\s*$",
                      [t for t, _ in rep.sections if t.startswith("CONFIGURATION —")],
                      "the config file name in the CONFIGURATION banner").group(1)
    groups: list[dict] = []
    for line in body:
        if m := re.match(r"--- (.+?) -{3,}\s*$", line):
            groups.append({"title": m.group(1).strip(), "lines": []})
        elif line.startswith("--- "):
            # `sub()` pads its rule to a fixed width, so a long enough group
            # title leaves fewer than three trailing dashes. Ignoring the line
            # would fold that group's lines into the PREVIOUS group — which
            # here means the exit levels get read as part of the config file,
            # and the page positively asserts that editing the file moves the
            # stops. Wrong-but-plausible is what this parser exists to prevent.
            raise ReportParseError(
                f"{rep.path}: CONFIGURATION group header not recognised: {line.strip()!r}"
            )
        elif groups:
            groups[-1]["lines"].append(line)
        elif line.strip():
            # Prose before the first group header is the section's intro.
            continue
    if len(groups) != 2:
        raise ReportParseError(
            f"{rep.path}: expected 2 CONFIGURATION groups (the config file, then the "
            f"frozen exits), found {len(groups)}: {[g['title'] for g in groups]}"
        )
    file_group, exits_group = groups
    if not file_group["title"].endswith(CONFIG_FILE_MARKER):
        raise ReportParseError(
            f"{rep.path}: first CONFIGURATION group {file_group['title']!r} is not the "
            f"config-file echo (expected a title ending {CONFIG_FILE_MARKER!r})"
        )
    if not exits_group["title"].startswith(CONFIG_EXITS_MARKER):
        raise ReportParseError(
            f"{rep.path}: second CONFIGURATION group {exits_group['title']!r} is not the "
            f"frozen exits (expected a title starting {CONFIG_EXITS_MARKER!r})"
        )
    return {
        "source": source,
        "file": _config_file_text(rep, file_group),
        "exits": _config_exit_rows(rep, exits_group),
        "exits_title": exits_group["title"],
    }


def _config_file_text(rep: Report, group: dict) -> str:
    """The echoed config file, with the report's body indent taken back off."""
    out = []
    for line in group["lines"]:
        if line and not line.startswith(CONFIG_FILE_INDENT):
            # Every echoed line carries the indent. One that does not is a line
            # the study did not print as file content — and dedenting it anyway
            # would put text into the page's config panel that is not in the
            # config file.
            raise ReportParseError(
                f"{rep.path}: CONFIGURATION file line is not indented as file "
                f"content: {line!r}"
            )
        out.append(line[len(CONFIG_FILE_INDENT):])
    text = "\n".join(out).strip("\n")
    if not text.strip():
        raise ReportParseError(f"{rep.path}: CONFIGURATION echoed an empty config file")
    return text


def _config_exit_rows(rep: Report, group: dict) -> list[dict]:
    rows = []
    for line in group["lines"]:
        if not line.strip():
            continue
        m = re.match(r"  (\S.*?)\s{4,}(\S.*?)\s*$", line)
        if not m:
            # A row that will not split on its 4-space separator is a row this
            # parser would otherwise drop — an exit level missing from the page
            # while every other assertion still passed.
            raise ReportParseError(
                f"{rep.path}: CONFIGURATION line in group {group['title']!r} "
                f"has no label/value separator: {line.strip()!r}"
            )
        rows.append({"label": m.group(1), "value": m.group(2)})
    if not rows:
        raise ReportParseError(
            f"{rep.path}: CONFIGURATION group {group['title']!r} has no rows"
        )
    return rows


def parse_structure_arm(rep: Report) -> dict | None:
    """The `--structure-universe` widening block, present only on that arm."""
    try:
        body = rep.body("STRUCTURE UNIVERSE")
    except ReportParseError:
        return None
    universe = rep.find(r"candidate universe (\d+) -> (\d+) rows \(([+-]\d+)\)", body, "the candidate-universe line")
    deployed = rep.find(r"deployed picks (\d+) -> (\d+)\s+dates (\d+) -> (\d+)", body, "the deployed-picks line")
    return {
        "universe_before": int(universe.group(1)),
        "universe_after": int(universe.group(2)),
        "deployed_before": int(deployed.group(1)),
        "deployed_after": int(deployed.group(2)),
        "dates_before": int(deployed.group(3)),
        "dates_after": int(deployed.group(4)),
    }


# --------------------------------------------------------------------------
# population-scoped sections
# --------------------------------------------------------------------------

def parse_baselines(rep: Report, pop: str) -> dict:
    body = rep.scoped(pop, "B1 / B2 BASELINES")
    out = {}
    for key in ("B1", "B2"):
        m = rep.find(
            rf"{key}\s+.+?n=\s*(\d+)\s+dates=\s*(\d+)\s+\$\s*([\d,\-]+)\s+meanR ([+-][\d.]+)",
            body,
            f"the {key} baseline line",
        )
        out[key] = {
            "n": int(m.group(1)),
            "dates": int(m.group(2)),
            "dollars": _num(m.group(3)),
            "meanR": float(m.group(4)),
        }
    out["ratio"] = _num(rep.find(r"B2/B1 dollar ratio ([\d.]+)x", body, "the B2/B1 ratio").group(1))
    return out


def parse_granularity(rep: Report, pop: str) -> dict:
    body = rep.scoped(pop, "GRANULARITY")
    accounts: list[dict] = []
    current: dict | None = None
    for line in body:
        if m := re.match(r"\s+\$([\d,]+) account / \$([\d,]+) budget", line):
            current = {"capital": _num(m.group(1)), "budget": _num(m.group(2)), "dist": {}}
            accounts.append(current)
        elif current is None:
            continue
        elif m := re.match(r"\s+contracts distribution: (.+)", line):
            body_text = m.group(1)
            current["dist_truncated"] = "..." in body_text
            for c, n in re.findall(r"(\d+)c:(\d+)", body_text):
                current["dist"][int(c)] = int(n)
        elif m := re.match(r"\s+mean ([\d.]+) contracts\s+median ([\d.]+)", line):
            current["mean_contracts"] = float(m.group(1))
            current["median_contracts"] = float(m.group(2))
        elif m := re.match(r"\s+1-contract FLOOR share\s+(\d+)/(\d+) \((\d+)%\)", line):
            current["floor_n"] = int(m.group(1))
            current["floor_of"] = int(m.group(2))
            current["floor_pct"] = int(m.group(3))
        elif m := re.match(r"\s+budget-BREACH share\s+(\d+)/(\d+) \((\d+)%\)", line):
            current["breach_n"] = int(m.group(1))
            current["breach_pct"] = int(m.group(3))
        elif m := re.match(
            r"\s+realized per-position risk %: median ([\d.]+)%\s+p90 ([\d.]+)%\s+max ([\d.]+)%", line
        ):
            current["risk_median"] = float(m.group(1))
            current["risk_p90"] = float(m.group(2))
            current["risk_max"] = float(m.group(3))
    if len(accounts) != 2:
        raise ReportParseError(f"{rep.path}: expected 2 account sizes in GRANULARITY, found {len(accounts)}")
    picks = rep.find(r"deployed picks (\d+)\s+with usable max_loss (\d+)\s+unsizable (\d+)", body, "the picks line")
    return {
        "accounts": accounts,
        "picks": int(picks.group(1)),
        "sizable": int(picks.group(2)),
        "unsizable": int(picks.group(3)),
    }


def parse_utilisation(rep: Report, pop: str) -> list[dict]:
    body = rep.scoped(pop, "UTILISATION")
    rows = []
    for line in body:
        m = re.match(
            r"\s+(\d{4}-\d\d)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"
            r"\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)\s*$",
            line,
        )
        if m:
            rows.append(
                {
                    "month": m.group(1),
                    "sessions": int(m.group(2)),
                    "res_avg": float(m.group(3)),
                    "res_max": float(m.group(4)),
                    "gross_avg": float(m.group(5)),
                    "gross_max": float(m.group(6)),
                    "net_avg": float(m.group(7)),
                    "net_max": float(m.group(8)),
                    "open_avg": float(m.group(9)),
                    "open_max": int(m.group(10)),
                }
            )
    if not rows:
        raise ReportParseError(f"{rep.path}: no monthly rows in [{POPULATIONS[pop]}] UTILISATION")
    return rows


def parse_arms(rep: Report, pop: str) -> list[dict]:
    body = rep.scoped(pop, "ARMS —")
    arms = []
    for line in body:
        m = re.match(
            r"\s+\((\w), (\w+)\)\s+(HEADLINE)?\s*(\d+)\s+(\d+)\s+([\d,\-]+)\s+([\d.\-]+)\s+(\d+)%\s+([\d,\-]+)\s*$",
            line,
        )
        if m:
            arms.append(
                {
                    "arm": f"({m.group(1)}, {m.group(2)})",
                    "headline": bool(m.group(3)),
                    "n": int(m.group(4)),
                    "dates": int(m.group(5)),
                    "dollars": _num(m.group(6)),
                    "meanR": float(m.group(7)),
                    "win": int(m.group(8)) / 100,
                    "maxDD": _num(m.group(9)),
                }
            )
    if len(arms) != 4:
        raise ReportParseError(f"{rep.path}: expected 4 arms for {pop}, found {len(arms)}")
    return arms


def parse_sleeve(rep: Report, pop: str) -> dict:
    body = rep.scoped(pop, "ARM H")
    out = {}
    label = None
    for line in body:
        if m := re.match(r"\s+(with|without) sleeve\s*$", line):
            label = "with" if m.group(1) == "with" else "without"
            out[label] = {}
        elif label is None:
            continue
        elif m := re.match(
            r"\s+signal positions\s+(\d+)\s+\$\s*([\d,\-]+)\s+sleeve positions\s+(\d+)\s+\$\s*([\d,\-]+)", line
        ):
            out[label].update(
                signal_n=int(m.group(1)),
                signal_dollars=_num(m.group(2)),
                sleeve_n=int(m.group(3)),
                sleeve_dollars=_num(m.group(4)),
            )
        elif m := re.match(
            r"\s+total \$\s*([\d,\-]+)\s+gross avg ([\d.]+)x max ([\d.]+)x\s+net avg ([\d.]+)x max ([\d.]+)x", line
        ):
            out[label].update(
                total=_num(m.group(1)),
                gross_avg=float(m.group(2)),
                gross_max=float(m.group(3)),
                net_avg=float(m.group(4)),
                net_max=float(m.group(5)),
            )
    if set(out) != {"with", "without"}:
        raise ReportParseError(f"{rep.path}: ARM H for {pop} missing a with/without sleeve block")
    return out


def parse_cap_grid(rep: Report, pop: str) -> dict:
    body = rep.scoped(pop, "CAP GRID")
    net_caps: list[str] = []
    rows: list[dict] = []
    for line in body:
        if m := re.match(r"\s+per-pos / net\s+(.+)", line):
            net_caps = m.group(1).split()
        elif net_caps and (m := re.match(r"\s+(inf|[\d.]+)\s+(.+)", line)):
            cells = re.findall(r"([\d,]+)/(\d+)", m.group(2))
            if len(cells) == len(net_caps):
                rows.append(
                    {
                        "per_pos": m.group(1),
                        "cells": [{"dollars": _num(d), "n": int(n)} for d, n in cells],
                    }
                )
    if not rows:
        raise ReportParseError(f"{rep.path}: could not parse the {pop} cap grid")
    headline = rep.find(
        r"per-pos (inf|[\d.]+) x net (inf|[\d.]+) \(the configured", body, "the headline cap cell"
    )
    hl = rep.find(r"n=(\d+)\s+dates=(\d+)\s+\$([\d,\-]+)\s+meanR ([+-][\d.]+)", body, "the headline cap numbers")
    mono_rows = rep.find(r"rows monotone in the net cap:\s+(\d+)/(\d+)", body, "the row monotonicity read")
    mono_cols = rep.find(r"columns monotone in the per-pos cap: (\d+)/(\d+)", body, "the column monotonicity read")
    return {
        "net_caps": net_caps,
        "rows": rows,
        "headline": {
            "per_pos": headline.group(1),
            "net": headline.group(2),
            "n": int(hl.group(1)),
            "dates": int(hl.group(2)),
            "dollars": _num(hl.group(3)),
            "meanR": float(hl.group(4)),
        },
        "monotone_rows": [int(mono_rows.group(1)), int(mono_rows.group(2))],
        "monotone_cols": [int(mono_cols.group(1)), int(mono_cols.group(2))],
    }


def parse_criteria(rep: Report, pop: str) -> list[dict]:
    """The A1-A6 checklist, plus any warning the study printed under a criterion.

    On the frozen report a criterion is exactly two lines. The compounding arm
    prints a block of prose under A2 and A5 saying those two do NOT transfer to
    it; that text is carried through verbatim (`warning`) so the compounding
    page can quote the study rather than paraphrase it. Nothing else in this
    section is prose, so anything trailing a verdict line is that block.
    """
    body = rep.scoped(pop, "CRITERIA A1-A6")
    out: list[dict] = []
    for line in body:
        if m := re.match(r"\s+(A\d) ([A-Z][A-Z .&-]*?)\s\s+(.+)", line):
            out.append({"id": m.group(1), "name": m.group(2).strip().title(),
                        "detail": m.group(3).strip(), "warning_lines": []})
        elif m := re.match(r"\s+(MET|NOT MET)\s+\((.+)\)\s*$", line):
            if not out:
                raise ReportParseError(f"{rep.path}: a criteria verdict preceded its criterion")
            out[-1]["status"] = m.group(1)
            out[-1]["needs"] = m.group(2)
        elif line.strip() and out and "status" in out[-1]:
            out[-1]["warning_lines"].append(line)
    if len(out) != 6 or any("status" not in c for c in out):
        raise ReportParseError(f"{rep.path}: expected 6 fully-parsed criteria for {pop}, got {out}")
    for c in out:
        c["warning"] = textwrap.dedent("\n".join(c.pop("warning_lines"))).strip()
        if m := re.search(r"CI95 \[([+-][\d.]+),([+-][\d.]+)\]", c["detail"]):
            c["ci"] = [float(m.group(1)), float(m.group(2))]
        if m := re.search(r"meanR ([+-][\d.]+)", c["detail"]):
            c["meanR"] = float(m.group(1))
        c["years"] = {y: float(v) for y, v in re.findall(r"(\d{4}):([+-][\d.]+)", c["detail"])}
    return out


# The compounding arm's re-mark table:
#   `<session>  <marked equity>  <budget>  <per-pos cap $>  <net cap $>  [flags]`
# Every column is a whole-dollar figure, so a row that lost one no longer
# matches and is reported as a count mismatch rather than silently dropped.
_MARKS_HEADER = re.compile(r"mark session\s+marked equity\s+budget\s+per-pos cap \$\s+net cap \$")
_MARK_ROW = re.compile(r"\s{2}(\S+)\s+(-?[\d,]+)\s+(-?[\d,]+)\s+(-?[\d,]+)\s+(-?[\d,]+)\s*(.*?)\s*$")


def parse_equity_marks(rep: Report, pop: str) -> dict | None:
    """`[<pop>] EQUITY MARKS`, the section only the compounding arm prints.

    Absent from the frozen, path-independent report — that is a no-op rather
    than a parse failure, so this returns None. PRESENT but changed IS a
    failure: the row count, the truncation line and the two summary lines must
    agree with each other, because the page quotes this table as the sizing
    path the run actually took. A table that silently lost rows would show a
    shorter, smoother equity path than the one that was simulated.
    """
    try:
        body = rep.scoped(pop, "EQUITY MARKS")
    except ReportParseError:
        return None
    friction = rep.find(r"mark interval \((\w+)\) and the (\S+) budget ceiling",
                        body, "the EQUITY MARKS friction-model line")
    rep.find(_MARKS_HEADER.pattern, body, "the EQUITY MARKS table header")

    note: list[str] = []
    marks: list[dict] = []
    seen_header = False
    truncated, print_cap = 0, None
    for line in body:
        if not seen_header:
            seen_header = bool(_MARKS_HEADER.search(line))
            if not seen_header:
                note.append(line)
        elif m := re.match(r"\s+\.\.\. (\d+) further marks not printed \(cap (\d+)\)", line):
            truncated, print_cap = int(m.group(1)), int(m.group(2))
        elif m := _MARK_ROW.match(line):
            marks.append({
                "session": m.group(1),
                "equity": _num(m.group(2)),
                "budget": _num(m.group(3)),
                "per_pos": _num(m.group(4)),
                "net": _num(m.group(5)),
                "flags": m.group(6).split(),
            })

    out = {
        "interval": friction.group(1),
        "ceiling": friction.group(2),
        # The study's own words for why this arm is a sensitivity and not the
        # book. Carried verbatim: the page quotes it rather than restating it.
        "note": textwrap.dedent("\n".join(note)).strip("\n").strip(),
        "marks": marks,
        "truncated": truncated,
        "print_cap": print_cap,
    }
    if not marks and any("no marks" in line for line in body):
        # A population with no signal dates re-marks nothing. The study says so
        # in one line and prints no summary, so there is nothing to cross-check.
        return {**out, "count": 0, "first": None, "peak": None, "final": None,
                "capital": None, "ceiling_bound": 0, "ruined": 0}
    total = rep.find(
        r"marks (\d+)\s+first \$(-?[\d,]+)\s+peak \$(-?[\d,]+)\s+final \$(-?[\d,]+)"
        r"\s+\(starting capital \$([\d,]+)\)",
        body, "the EQUITY MARKS summary line")
    bound = rep.find(r"budget ceiling bound on (\d+) of (\d+) marks; ruin guard fired on (\d+)",
                     body, "the EQUITY MARKS ceiling/ruin line")
    count = int(total.group(1))
    if len(marks) + truncated != count:
        raise ReportParseError(
            f"{rep.path}: [{POPULATIONS[pop]}] EQUITY MARKS says {count} marks but "
            f"{len(marks)} rows parsed plus {truncated} truncated"
        )
    if int(bound.group(2)) != count:
        raise ReportParseError(
            f"{rep.path}: [{POPULATIONS[pop]}] EQUITY MARKS summary says {count} marks, "
            f"its ceiling line says {bound.group(2)}"
        )
    return {
        **out,
        "count": count,
        "first": _num(total.group(2)),
        "peak": _num(total.group(3)),
        "final": _num(total.group(4)),
        "capital": _num(total.group(5)),
        "ceiling_bound": int(bound.group(1)),
        "ruined": int(bound.group(3)),
    }


def parse_equity_summary(rep: Report, pop: str) -> dict:
    body = rep.scoped(pop, "EQUITY CURVE")
    out = {}
    for key, label in (("constrained", r"constrained\s"), ("b2", r"B2 unconstrained")):
        m = rep.find(
            rf"{label}\s+sessions=\s*(\d+)\s+total \$\s*([\d,\-]+)\s+maxDD \$\s*([\d,\-]+)"
            rf"\s+worst session \$\s*([\d,\-]+)",
            body,
            f"the {key} equity-curve line",
        )
        out[key] = {
            "sessions": int(m.group(1)),
            "total": _num(m.group(2)),
            "maxDD": _num(m.group(3)),
            "worst": _num(m.group(4)),
        }
    dd = rep.find(r"constrained maxDD ([\d.]+)% of \$([\d,]+) starting capital \(A3 limit (\d+)%\)",
                  body, "the A3 line")
    out["dd_pct"] = float(dd.group(1))
    out["capital"] = _num(dd.group(2))
    out["dd_limit_pct"] = float(dd.group(3))
    return out


def parse_adverse(rep: Report, pop: str) -> dict:
    body = rep.scoped(pop, "ADVERSE-ORDERING CHECK")
    taken = rep.find(r"taken\s+n=\s*(\d+)\s+meanR ([+-][\d.]+)", body, "the adverse-ordering taken line")
    rejected = []
    for line in body:
        if m := re.match(
            r"\s+rejected \[(\w+)\s*\] n=\s*(\d+)\s+meanR ([+-][\d.]+)\s+delta vs taken ([+-][\d.]+)", line
        ):
            rejected.append(
                {
                    "bucket": m.group(1),
                    "n": int(m.group(2)),
                    "meanR": float(m.group(3)),
                    "delta": float(m.group(4)),
                }
            )
    if not rejected:
        raise ReportParseError(f"{rep.path}: no rejected buckets parsed from ADVERSE-ORDERING CHECK")
    return {"taken": {"n": int(taken.group(1)), "meanR": float(taken.group(2))}, "rejected": rejected}


def parse_census(rep: Report, pop: str) -> dict:
    body = rep.scoped(pop, "BINDING-CONSTRAINT CENSUS")
    buckets = {}
    for line in body:
        # Any `  <lowercase_bucket>   <count>` line, not a fixed whitelist: the
        # study can add a bucket (ARM H emits hedge_taken/hedge_rejected) and a
        # whitelist here would drop it, which is the one thing the census may
        # never do. The section's other lines start uppercase, so they miss.
        if m := re.match(r"\s+([a-z][a-z0-9_]*)\s+(\d+)\s*$", line):
            buckets[m.group(1)] = int(m.group(2))
    total = rep.find(r"TOTAL considered\s+(\d+)", body, "the census total")
    most = rep.find(r"MOST BINDING constraint: (\w+) \((\d+) of (\d+) exclusions\)", body, "the most-binding line")
    return {
        "buckets": buckets,
        "total": int(total.group(1)),
        "most_binding": most.group(1),
        "most_binding_n": int(most.group(2)),
        "exclusions": int(most.group(3)),
    }


_CELL_ROW = re.compile(
    r"\s+(\S+)\s+(\S+)\s+(\d+)\s+(-?[\d,]+)\s+([+-][\d.]+)\s+([\d.]+)(\s+thin)?\s*$"
)


def _cell_rows(lines: list[str]) -> tuple[list[dict], dict | None]:
    """`cell structure n dollars meanR win [thin]` rows out of one sub-block.

    The per-cell `ALL` rollups are dropped — they are a reading aid in the text
    report and would double-count anything summed here. `TOTAL ALL` is returned
    separately, because reconciliation checks it against the population's own
    headline rather than against the cells.
    """
    cells, total = [], None
    for line in lines:
        if not (m := _CELL_ROW.match(line)):
            continue
        row = {
            "cell": m.group(1),
            "structure": m.group(2),
            "n": int(m.group(3)),
            "dollars": float(m.group(4).replace(",", "")),
            "meanR": float(m.group(5)),
            "win": float(m.group(6)),
            "thin": bool(m.group(7)),
        }
        if row["cell"] == "TOTAL":
            total = row
        elif row["structure"] != "ALL":
            cells.append(row)
    return cells, total


def _sub_block(rep: Report, body: list[str], startswith: str) -> list[str]:
    """Lines of one `--- <title> ---` sub-block, up to the next one."""
    out, inside = [], False
    for line in body:
        if line.startswith("--- "):
            if inside:
                break
            inside = line.startswith(f"--- {startswith}")
            continue
        if inside:
            out.append(line)
    if not out:
        raise ReportParseError(f"{rep.path}: no {startswith!r} block in DEPLOYED BOOK BY REGIME")
    return out


def parse_regime(rep: Report, pop: str) -> dict:
    """Parse `[<pop>] DEPLOYED BOOK BY REGIME`, the study's post-hoc regime cut.

    Nothing here is whitelisted to the regime cells that happen to exist today
    (BEAR_HE / LVOL / RB_EVOL / PROD): a fifth cell must surface rather than be
    silently dropped, the same principle `parse_census` states for buckets.
    """
    body = rep.scoped(pop, "DEPLOYED BOOK BY REGIME")

    mech, mech_total = _cell_rows(_sub_block(rep, body, "MECHANICAL cell x structure"))
    model, model_total = _cell_rows(_sub_block(rep, body, "MODEL regime cell x structure"))
    if not mech or not model or mech_total is None or model_total is None:
        raise ReportParseError(f"{rep.path}: DEPLOYED BOOK BY REGIME has an empty cell table")

    census, census_total = [], None
    for line in _sub_block(rep, body, "deployment census by mechanical cell"):
        if m := re.match(r"\s+(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d,]+)\s+([\d,]+)\s*$", line):
            row = {
                "cell": m.group(1),
                "n": int(m.group(2)),
                "tierA": int(m.group(3)),
                "tierB": int(m.group(4)),
                "reserved": float(m.group(5).replace(",", "")),
                "dn": float(m.group(6).replace(",", "")),
            }
            if row["cell"] == "TOTAL":
                census_total = row
            else:
                census.append(row)

    skips, considered = [], None
    for line in _sub_block(rep, body, "what the caps SKIPPED"):
        if m := re.match(r"\s+(\S+)\s+([a-z][a-z0-9_]*)\s+(\d+)\s*$", line):
            if m.group(1) == "TOTAL":
                considered = int(m.group(3))
            else:
                skips.append({"cell": m.group(1), "bucket": m.group(2), "n": int(m.group(3))})

    agreement, same, total = [], None, None
    agree_body = _sub_block(rep, body, "model read vs mechanical read")
    for line in agree_body:
        if m := re.match(r"\s+([A-Z][A-Z_]*)\s+([A-Z][A-Z_]*)\s+(\d+)\s*$", line):
            agreement.append({"model": m.group(1), "mech": m.group(2), "n": int(m.group(3))})
    m = rep.find(r"agreement (\d+) of (\d+) \(([\d.]+)\)", agree_body, "the regime agreement line")
    same, total = int(m.group(1)), int(m.group(2))

    if not census or not skips or not agreement or considered is None or census_total is None:
        raise ReportParseError(f"{rep.path}: DEPLOYED BOOK BY REGIME is missing rows")
    return {
        "mech": mech, "mech_total": mech_total,
        "model": model, "model_total": model_total,
        "census": census, "census_total": census_total,
        "skips": skips, "considered": considered,
        "agreement": agreement, "agree": same, "agree_total": total,
    }


def parse(path: Path) -> dict:
    """Parse a full account_sim report into the renderer's data dict."""
    rep = Report(path.read_text(), path)
    out: dict = {
        "provenance": parse_provenance(rep),
        "account_config": parse_account_config(rep),
        "configuration": parse_configuration(rep),
        "gates": parse_gates(rep),
        "population_notes": parse_episodes(rep),
        "verdict": parse_verdict(rep),
        "structure_arm": parse_structure_arm(rep),
        "populations": {},
    }
    for pop in POPULATIONS:
        out["populations"][pop] = {
            "baselines": parse_baselines(rep, pop),
            "granularity": parse_granularity(rep, pop),
            "utilisation": parse_utilisation(rep, pop),
            "arms": parse_arms(rep, pop),
            "sleeve": parse_sleeve(rep, pop),
            "cap_grid": parse_cap_grid(rep, pop),
            "criteria": parse_criteria(rep, pop),
            "equity": parse_equity_summary(rep, pop),
            # None on the frozen report — the section exists only under
            # --compounding, and only that arm's page draws it.
            "equity_marks": parse_equity_marks(rep, pop),
            "adverse": parse_adverse(rep, pop),
            "census": parse_census(rep, pop),
            "regime": parse_regime(rep, pop),
        }
    return out
