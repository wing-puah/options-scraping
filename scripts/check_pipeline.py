"""Collection-tier watchdog: fail loudly when the pipeline has silently stopped.

The scrape → compile → enrich chain runs unattended in GitHub Actions and
notifies nobody. GitHub emails the repo owner when a SCHEDULED WORKFLOW FAILS,
which covers exactly one failure mode — a job that ran and crashed. It does not
cover the ones that actually bite:

  * `enrich-oi.yml`, `fetch-counterpart-iv.yml` and `backfill-mech-cell.yml`
    have NO cron. All three trigger on `workflow_run` off Compile Flow, gated on
    its success. If Compile Flow fails or is skipped they never fire — and a job
    that never ran emails nobody.
  * GitHub silently DROPS scheduled runs under load.
  * GitHub DISABLES scheduled workflows after 60 days with no repo commits.
  * A step exits 0 having done nothing (auth quietly returning empty).

So this script asserts the EVIDENCE instead of the exit status: for every recent
trading session, did each stage leave what it is supposed to leave, and is it as
complete as it is supposed to be. A gap exits non-zero, which is the email.

Two traps this is built around — both would render the check worse than useless:

  1. THE STALE-CALENDAR TRAP. The obvious "was there a session?" source is
     `spy-vix-daily.csv`, but Compile Flow WRITES that file. A dead pipeline
     means a stale calendar, so the checker would conclude "no session, nothing
     expected, all clear" precisely when everything is broken. This script
     therefore fetches SPY from yfinance itself, and treats a failed fetch as a
     hard error (never a pass). The repo deliberately keeps no holiday table
     (see scripts/journal/lib/analysis.py) — a live SPY bar IS the calendar.

  2. THE GC TRAP. `gc_flow.py --all` runs inside Compile Flow and TRASHES raw
     snapshots once they are verified present in the compiled file. For any past
     session `snapshots == 0` is the HEALTHY steady state, so scrape evidence
     must accept a compiled file in their place.

Verdict logic (`evaluate`/`summarise`) is pure and unit-tested; everything that
touches Drive, Sheets, yfinance or the clock lives in the I/O half below.

Run:
    python3 scripts/check_pipeline.py
    python3 scripts/check_pipeline.py --as-of 2026-08-20 --verbose
"""
from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
# The enrichment-coverage helpers live beside the enrichers, in scripts/collector/.
sys.path.insert(0, str(ROOT / "scripts" / "collector"))

log = logging.getLogger("check_pipeline")

CONFIG_PATH = ROOT / "config" / "pipeline-health.yml"
BASELINE_TAB = "BaselineDaily"

EXIT_OK = 0
EXIT_GAP = 1          # the alarm — one or more stages missing or incomplete
EXIT_USAGE = 2        # bad config / bad arguments
EXIT_UNGROUNDED = 3   # could not reach yfinance or Drive — never reported as a pass

OK, MISSING, PARTIAL, NOT_DUE, UNKNOWN = "ok", "MISSING", "PARTIAL", "not-due", "UNKNOWN"
FAILING = (MISSING, PARTIAL, UNKNOWN)

_GLYPH = {OK: "ok", MISSING: "MISS", PARTIAL: "PART", NOT_DUE: "-", UNKNOWN: "?"}

# GitHub renders at most 10 annotations per step; past that they vanish silently.
MAX_ANNOTATIONS = 10


class StageSpec(NamedTuple):
    name: str
    kind: str
    lag_sessions: int
    min_complete: float
    prefixes: tuple[str, ...]
    field: str


class Finding(NamedTuple):
    stage: str
    session: str
    verdict: str
    detail: str


class HealthConfig(NamedTuple):
    stages: tuple[StageSpec, ...]
    lookback_sessions: int
    max_silence_sessions: int
    commit_age_warn_days: int
    chain_complete_utc_hour: int


# ── config ──────────────────────────────────────────────────────────────────

def load_config(path: Path = CONFIG_PATH) -> HealthConfig:
    """Parse config/pipeline-health.yml. Raises ValueError on a malformed spec."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    stages = []
    for entry in raw.get("stages") or []:
        if not entry.get("name") or not entry.get("kind"):
            raise ValueError(f"stage entry missing name/kind: {entry!r}")
        stages.append(StageSpec(
            name=entry["name"],
            kind=entry["kind"],
            lag_sessions=int(entry.get("lag_sessions", 0)),
            min_complete=float(entry.get("min_complete", 1.0)),
            prefixes=tuple(entry.get("prefixes") or ()),
            field=entry.get("field", ""),
        ))
    if not stages:
        raise ValueError(f"{path} defines no stages")
    return HealthConfig(
        stages=tuple(stages),
        lookback_sessions=int(raw.get("lookback_sessions", 10)),
        max_silence_sessions=int(raw.get("max_silence_sessions", 3)),
        commit_age_warn_days=int(raw.get("commit_age_warn_days", 45)),
        chain_complete_utc_hour=int(raw.get("chain_complete_utc_hour", 23)),
    )


# ── pure verdict logic ──────────────────────────────────────────────────────

def _coverage_verdict(cov, min_complete: float, unit: str) -> tuple[str, str]:
    """`(verdict, detail)` for a (done, total) coverage pair. Pure."""
    if cov is None:
        return MISSING, "no compiled file to enrich"
    done, total = cov
    if total == 0:
        # A genuinely thin session has nothing to enrich. Calling that a failure
        # is how a checker starts crying wolf on quiet days.
        return OK, f"no {unit} to enrich"
    pct = done / total
    detail = f"{done}/{total} {unit} ({pct:.0%}, need {min_complete:.0%})"
    return (OK if pct >= min_complete else PARTIAL), detail


def _judge(stage: StageSpec, session: str, state: dict) -> Finding:
    """One stage's verdict for one session. Pure — reads `state`, touches nothing."""
    flow = state.get("flow", {}).get(session, {})

    if stage.kind == "flow_present":
        # THE GC TRAP: snapshots are trashed once compiled, so `snapshots == 0`
        # with a compiled file present is the healthy steady state for any past
        # session. Either form of evidence counts.
        missing = [p for p in stage.prefixes
                   if not (flow.get(p, {}).get("compiled")
                           or flow.get(p, {}).get("snapshots", 0) > 0)]
        if missing:
            return Finding(stage.name, session, MISSING,
                           f"no flow data for {', '.join(missing)}")
        have = sum(flow.get(p, {}).get("snapshots", 0) for p in stage.prefixes)
        return Finding(stage.name, session, OK,
                       f"{have} snapshot(s)" if have else "compiled (snapshots GC'd)")

    if stage.kind == "compiled_present":
        missing = [p for p in stage.prefixes if not flow.get(p, {}).get("compiled")]
        if missing:
            return Finding(stage.name, session, MISSING,
                           f"no compiled file for {', '.join(missing)}")
        return Finding(stage.name, session, OK, "compiled")

    if stage.kind == "enrichment":
        per_prefix = state.get("enrich", {}).get(session, {})
        unit = "contracts" if stage.field == "oi" else "tickers"
        worst = None
        for prefix in stage.prefixes:
            cov = per_prefix.get(prefix, {}).get(stage.field)
            verdict, detail = _coverage_verdict(cov, stage.min_complete, unit)
            if verdict != OK:
                return Finding(stage.name, session, verdict, f"{prefix}: {detail}")
            worst = detail
        return Finding(stage.name, session, OK, worst or "nothing to enrich")

    if stage.kind == "counterpart":
        cov = state.get("counterpart", {}).get(session)
        verdict, detail = _coverage_verdict(cov, stage.min_complete, "legs")
        if cov is None:
            detail = "no sidecar"
        return Finding(stage.name, session, verdict, detail)

    if stage.kind == "baseline_row":
        if session in state.get("baseline", set()):
            return Finding(stage.name, session, OK, "row present")
        return Finding(stage.name, session, MISSING, f"no {BASELINE_TAB} row")

    return Finding(stage.name, session, UNKNOWN, f"unknown stage kind {stage.kind!r}")


def settled_sessions(sessions: list[str], now_utc: datetime,
                     chain_complete_utc_hour: int) -> list[str]:
    """The sessions whose end-of-day chain has plausibly finished. Pure.

    Compile Flow fires at 22:30 UTC on the session it compiles, and the enrich
    chain follows it. A session is therefore still IN FLIGHT until late on its
    own UTC date: right now, mid-session, none of its downstream evidence exists
    yet and demanding it would be a false alarm.

    This costs nothing in CI — the watchdog runs at 01:45 UTC, when the newest
    trading session is already the previous UTC date — but it is what stops a
    hand-run check during market hours from crying wolf, which is how an
    operator learns to ignore the alarm.
    """
    today = now_utc.strftime("%Y-%m-%d")
    if now_utc.hour >= chain_complete_utc_hour:
        return list(sessions)
    return [s for s in sessions if s < today]


def evaluate(state: dict, stages, sessions: list[str],
             settled: list[str] | None = None) -> list[Finding]:
    """Verdicts for every (stage, session) pair. Pure — no I/O, no clock.

    A stage's newest `lag_sessions` sessions are reported not-due rather than
    missing: `enrich_oi` is structurally D+1 (OI CHANGE for session D needs D+1's
    open interest), so "yesterday's OI is incomplete" is normal, not a fault.
    Lag is counted in SESSIONS, not calendar days, so a Friday check never walks
    back into the weekend. `settled` (default: all of them) further excludes any
    session whose end-of-day chain has not plausibly run yet.
    """
    n_settled = len(sessions) if settled is None else len(settled)
    findings: list[Finding] = []
    for stage in stages:
        # Lag counts back from the newest SETTLED session, not the newest
        # session: if today is still in flight, yesterday's OI is not due either
        # — it needs today's open interest, which does not exist yet.
        cut = min(n_settled, len(sessions)) - stage.lag_sessions
        for session in sessions[:max(cut, 0)]:
            findings.append(_judge(stage, session, state))
        for session in sessions[max(cut, 0):]:
            reason = ("session still in flight — its end-of-day chain has not run yet"
                      if session not in (settled if settled is not None else sessions)
                      else f"within this stage's {stage.lag_sessions}-session lag")
            findings.append(Finding(stage.name, session, NOT_DUE, reason))
    return findings


def silence_gap(state: dict, sessions: list[str]) -> int:
    """How many of the newest sessions hold NO flow data at all. Pure.

    Distinguishes "one enricher is behind" from "nothing has run for a week",
    which deserve very different headlines.
    """
    flow = state.get("flow", {})
    gap = 0
    for session in reversed(sessions):
        entry = flow.get(session) or {}
        if any(v.get("compiled") or v.get("snapshots", 0) > 0 for v in entry.values()):
            break
        gap += 1
    return gap


def summarise(findings: list[Finding], sessions: list[str], as_of: str,
              silence: int, commit_age_days: int | None,
              cfg: HealthConfig) -> tuple[int, str]:
    """`(exit_code, report)`. Pure.

    The GitHub failure email carries only the job name and a link, so the first
    lines of this report have to name the gap — it is what the operator reads.
    """
    gaps = [f for f in findings if f.verdict in FAILING]
    alarms: list[str] = []

    if silence >= cfg.max_silence_sessions:
        newest = sessions[-silence - 1] if silence < len(sessions) else "never"
        alarms.append(f"PIPELINE SILENT: no flow data for the last {silence} session(s) "
                      f"(newest data: {newest})")
    if commit_age_days is not None and commit_age_days > cfg.commit_age_warn_days:
        alarms.append(
            f"REPO QUIET: last commit was {commit_age_days} days ago. GitHub disables "
            f"scheduled workflows after 60 days without a commit — including THIS one. "
            f"Push anything to reset the clock.")

    failed = bool(gaps or alarms)
    head = "FAILED" if failed else "OK"
    lines = [f"PIPELINE HEALTH — {head} (as-of {as_of}, {len(sessions)} session(s) checked)", ""]
    for a in alarms:
        lines += [f"  {a}", ""]

    stage_names = list(dict.fromkeys(f.stage for f in findings))
    by_key = {(f.stage, f.session): f for f in findings}
    width = max((len(s) for s in stage_names), default=0) + 2
    lines.append("  " + "stage".ljust(width) + "".join(s[5:].rjust(7) for s in sessions))
    for name in stage_names:
        row = "".join(_GLYPH.get(by_key[(name, s)].verdict, "?").rjust(7)
                      if (name, s) in by_key else "".rjust(7) for s in sessions)
        lines.append("  " + name.ljust(width) + row)
    lines.append("")

    if gaps:
        lines.append(f"  {len(gaps)} gap(s):")
        for f in gaps:
            lines.append(f"    {f.session}  {f.stage:<16} {f.verdict:<8} {f.detail}")
    elif not alarms:
        lines.append("  Every due stage left the evidence it should have.")
    lines.append("")

    return (EXIT_GAP if failed else EXIT_OK), "\n".join(lines)


# ── I/O ─────────────────────────────────────────────────────────────────────

def sessions_from_yfinance(start: str, end: str) -> list[str]:
    """Real trading sessions in [start, end], from a LIVE SPY query.

    Deliberately NOT read from `spy-vix-daily.csv`: Compile Flow writes that
    file, so a dead pipeline would leave a stale calendar and this checker would
    report "no session, nothing expected, all clear" exactly when everything is
    broken. Asking SPY directly also sidesteps that file's known one-legged
    holiday rows (research/current.md — a VIX close with an empty SPY close),
    since there is no second series to disagree.

    Raises RuntimeError rather than returning an empty list: a calendar we could
    not ground must never be mistaken for "there were no sessions".
    """
    import pandas as pd
    import yfinance as yf

    end_padded = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        spy = yf.download("SPY", start=start, end=end_padded,
                          auto_adjust=False, progress=False)
    except Exception as e:                                   # noqa: BLE001
        raise RuntimeError(f"yfinance SPY download failed: {e}") from e
    if spy is None or spy.empty:
        raise RuntimeError("yfinance SPY download returned no rows")

    # Newer yfinance nests single-ticker frames under a MultiIndex.
    close = spy["Close"].iloc[:, 0] if isinstance(spy.columns, pd.MultiIndex) else spy["Close"]
    close = close.dropna()          # a session counts only if its close parses
    return [d.strftime("%Y-%m-%d") for d in pd.to_datetime(close.index)]


def _commit_age_days(as_of: date) -> int | None:
    """Days since the newest commit, or None if git is unavailable."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%ct"], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
        if out.returncode != 0 or not out.stdout.strip():
            return None
        committed = datetime.fromtimestamp(int(out.stdout.strip())).date()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return (as_of - committed).days


def collect_state(client, stages, sessions: list[str]) -> dict:
    """Fetch every fact `evaluate()` needs. All Drive/Sheets I/O happens here."""
    from lib import sheets_client
    from lib.csv_utils import parse_csv
    from compile_flow import FLOW_PREFIXES
    from enrich_oi import _source_file
    from update_enrich_logs import _check_cp, _iv_fields, _oi_fields, _price_fields

    wanted = sorted({p for s in stages for p in s.prefixes} | set(FLOW_PREFIXES))
    # One bounded sweep of the whole corpus (~1 query per prefix) rather than
    # 2-6 calls per date, which grows without limit as the corpus does.
    corpus = client.flow_corpus(wanted)
    flow = {d: {p: dict(v) for p, v in per_prefix.items()}
            for d, per_prefix in corpus.files.items()}

    needs_enrich = {s.field for s in stages if s.kind == "enrichment"}
    needs_cp = any(s.kind == "counterpart" for s in stages)
    enrich_prefixes = sorted({p for s in stages if s.kind == "enrichment" for p in s.prefixes})

    enrich: dict[str, dict] = {}
    counterpart: dict[str, tuple[int, int] | None] = {}
    for session in sessions:
        if needs_enrich:
            per_prefix: dict[str, dict] = {}
            for prefix in enrich_prefixes:
                file_id, file_name = _source_file(client, prefix, session)
                if not file_id:
                    per_prefix[prefix] = {f: None for f in needs_enrich}
                    continue
                rows = parse_csv(client.download(file_id, name=file_name))
                cov: dict[str, tuple[int, int] | None] = {}
                if "oi" in needs_enrich:
                    f = _oi_fields(rows)
                    cov["oi"] = (f["enriched_contracts"], f["total_contracts"])
                if "iv" in needs_enrich:
                    f = _iv_fields(rows)
                    cov["iv"] = (f["iv_enriched_tickers"], f["iv_total_tickers"])
                if "price" in needs_enrich:
                    f = _price_fields(rows)
                    cov["price"] = (f["price_enriched_tickers"], f["price_total_tickers"])
                per_prefix[prefix] = cov
            enrich[session] = per_prefix
        if needs_cp:
            cp = _check_cp(client, session)
            counterpart[session] = (None if cp["cp_status"] == "no-compiled"
                                    else (cp["cp_fetched"], cp["cp_wanted"]))

    baseline: set[str] = set()
    if any(s.kind == "baseline_row" for s in stages):
        try:
            # Raw strings, not evaluated values — these dates are keys and must
            # not be run through locale coercion.
            header, rows = sheets_client.get_all_values(BASELINE_TAB)
            if header and "date" in header:
                i = header.index("date")
                baseline = {r[i].strip() for r in rows if len(r) > i and r[i].strip()}
        except Exception as e:                               # noqa: BLE001
            log.warning("Could not read %s: %s", BASELINE_TAB, e)

    return {"flow": flow, "enrich": enrich, "counterpart": counterpart, "baseline": baseline}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as-of", help="date to check as of (YYYY-MM-DD); default today")
    ap.add_argument("--config", default=str(CONFIG_PATH), help="stage spec YAML")
    ap.add_argument("--verbose", action="store_true", help="log every verdict, not just gaps")
    args = ap.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)

    try:
        cfg = load_config(Path(args.config))
    except (OSError, ValueError, yaml.YAMLError) as e:
        log.error("bad config: %s", e)
        return EXIT_USAGE
    try:
        as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    except ValueError:
        log.error("--as-of must be YYYY-MM-DD, got %r", args.as_of)
        return EXIT_USAGE

    # Pad the window generously: lookback is counted in SESSIONS, and holidays
    # plus weekends mean calendar days run well ahead of sessions.
    start = (as_of - timedelta(days=cfg.lookback_sessions * 2 + 20)).isoformat()
    try:
        all_sessions = sessions_from_yfinance(start, as_of.isoformat())
    except RuntimeError as e:
        log.error("%s", e)
        log.error("Cannot tell which days were trading sessions — refusing to "
                  "report a verdict rather than pass by default.")
        return EXIT_UNGROUNDED

    sessions = [s for s in all_sessions if s <= as_of.isoformat()][-cfg.lookback_sessions:]
    if not sessions:
        log.error("No trading sessions found on or before %s", as_of)
        return EXIT_UNGROUNDED

    try:
        from lib.drive_client import get_drive_client
        client = get_drive_client()
        state = collect_state(client, cfg.stages, sessions)
    except Exception as e:                                   # noqa: BLE001
        log.error("could not read the pipeline's output: %s", e)
        log.error("Refusing to report a verdict on state we could not fetch.")
        return EXIT_UNGROUNDED

    settled = settled_sessions(sessions, datetime.now(timezone.utc),
                               cfg.chain_complete_utc_hour)
    findings = evaluate(state, cfg.stages, sessions, settled)
    code, report = summarise(findings, sessions, as_of.isoformat(),
                             silence_gap(state, sessions),
                             _commit_age_days(as_of), cfg)
    print(report)

    if code != EXIT_OK and os.getenv("GITHUB_ACTIONS") == "true":
        # Renders on the run's summary page, so the gap is visible without
        # opening the raw log. GitHub only shows the first 10 annotations per
        # step, so cap deliberately and SAY what was dropped — a silent
        # truncation reads as "that was all of it", which is the same lie this
        # whole script exists to catch. The full list is in the report above.
        gaps = [f for f in findings if f.verdict in FAILING]
        for f in gaps[:MAX_ANNOTATIONS]:
            print(f"::error title={f.stage} gap on {f.session}::{f.detail}")
        if len(gaps) > MAX_ANNOTATIONS:
            print(f"::error title=more gaps::{len(gaps) - MAX_ANNOTATIONS} further gap(s) "
                  f"not annotated — see the full table in the step log")
    return code


if __name__ == "__main__":
    sys.exit(main())
