"""Parse an `account_sim` text report into a dict the renderer can draw.

The report is a fixed-width artifact written for a human reader, so this parser
is deliberately strict: every section it wants is looked up by its exact banner
title, and a missing section raises rather than yielding an empty chart. A study
report that changed shape should break the build loudly — a chart drawn from a
half-parsed report is worse than no chart.
"""
from __future__ import annotations

import re
from pathlib import Path

BANNER = "=" * 78
POPULATIONS = {"primary": "PRIMARY dense episodes", "secondary": "SECONDARY full book"}


class ReportParseError(RuntimeError):
    """The report did not contain a section this renderer needs."""


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


# --------------------------------------------------------------------------
# whole-report sections
# --------------------------------------------------------------------------

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
        elif m := re.match(r"\s+([\d,]+) rows\s+(\S+ \S+)\s+(.+)", line):
            out["inputs"].append(
                {"rows": int(m.group(1).replace(",", "")), "mtime": m.group(2), "path": m.group(3).strip()}
            )
    for key in ("run_at", "command", "git"):
        if key not in out:
            raise ReportParseError(f"{rep.path}: provenance header missing {key!r}")
    out["structure_arm"] = "--structure-universe" in out["command"]
    return out


def parse_gates(rep: Report) -> dict:
    body = rep.body("GATES —")
    gates = []
    for line in body:
        if m := re.match(r"\s+(G\d): (PASS|FAIL)(.*)", line):
            gates.append({"id": m.group(1), "status": m.group(2), "note": m.group(3).strip()})
    if len(gates) != 5:
        raise ReportParseError(f"{rep.path}: expected 5 gate verdicts, found {len(gates)}")
    headline = rep.find(r"GATES: (.+)", body, "the GATES summary line").group(1).strip()
    titles = {
        "G1": "Book calibration quoted, B1 line reproduced",
        "G2": "Scaling identity calibrated at scale=1 against stored rows",
        "G3": "Ledger accounting identity, checked after every event",
        "G4": "Unconstrained walk reproduces top_k_per_day by set equality",
        "G5": "The simulator is blind to how a position turned out",
    }
    for g in gates:
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
    body = rep.scoped(pop, "CRITERIA A1-A6")
    out: list[dict] = []
    for line in body:
        if m := re.match(r"\s+(A\d) ([A-Z][A-Z .&-]*?)\s\s+(.+)", line):
            out.append({"id": m.group(1), "name": m.group(2).strip().title(), "detail": m.group(3).strip()})
        elif m := re.match(r"\s+(MET|NOT MET)\s+\((.+)\)\s*$", line):
            if not out:
                raise ReportParseError(f"{rep.path}: a criteria verdict preceded its criterion")
            out[-1]["status"] = m.group(1)
            out[-1]["needs"] = m.group(2)
    if len(out) != 6 or any("status" not in c for c in out):
        raise ReportParseError(f"{rep.path}: expected 6 fully-parsed criteria for {pop}, got {out}")
    for c in out:
        if m := re.search(r"CI95 \[([+-][\d.]+),([+-][\d.]+)\]", c["detail"]):
            c["ci"] = [float(m.group(1)), float(m.group(2))]
        if m := re.search(r"meanR ([+-][\d.]+)", c["detail"]):
            c["meanR"] = float(m.group(1))
        c["years"] = {y: float(v) for y, v in re.findall(r"(\d{4}):([+-][\d.]+)", c["detail"])}
    return out


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
            "adverse": parse_adverse(rep, pop),
            "census": parse_census(rep, pop),
            "regime": parse_regime(rep, pop),
        }
    return out
