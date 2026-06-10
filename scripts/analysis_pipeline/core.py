"""
Core logic for the options flow analysis pipeline.

    fetch    → prepare_analysis.fetch_data            (deterministic)
    analyze  → headless engine call (claude / codex)  (LLM, isolated context)
    write    → sheets_client.append_rows(tab)         (deterministic)

The only LLM touchpoint is a single headless call per date, run from a neutral
working directory so the framework, method file, and raw flow data are never
loaded into the *calling* agent's context. All operator-facing knobs live in
`config.py`; this module is the plumbing that wires them together.

Determinism note: the plumbing (fetch, prompt assembly, row expansion, write) is
deterministic; the analysis step is not — there is no temperature knob over the
headless CLIs, so expect run-to-run variation. We constrain it with a fixed
prompt + explicit JSON contract and retry on parse failure, nothing more.
"""
from scripts.prepare_analysis import (
    _last_n_trading_days,
    _latest_available_date,
    fetch_data,
)
from lib.drive_client import get_drive_client
from lib import sheets_client
from lib.logger import setup_logging
import argparse
import json
import logging
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv

from . import config
from .config import ENGINES, ROW_COLUMNS

load_dotenv(config.ROOT / ".env")
sys.path.insert(0, str(config.ROOT))


log = logging.getLogger("analysis_pipeline")


def _strip_output_section(framework_md: str) -> str:
    """Drop the framework's flat-schema '## Output Format' tail; we supply our own."""
    return framework_md.split("## Output Format", 1)[0].rstrip()


def build_prompt(framework_md: str, method_md: str, data_md: str, date_str: str) -> str:
    """Assemble the full self-contained analysis prompt for the headless engine."""
    return "\n\n".join([
        "# Options flow analysis",
        "You are analyzing options flow data. Apply the method to the "
        "data and return the JSON described at the end. Work only from what is "
        "in this prompt — do not run commands or read files.",
        f"Date being analyzed: {date_str}",
        "## Method (judgment)\n\n" + method_md,
        "## Framework (vocabulary)\n\n" + _strip_output_section(framework_md),
        config.ANALYSIS_PROMPT_CONTRACT,
        "## Fetched data\n\n" + data_md,
    ])


def _extract_json(text: str) -> dict:
    """Pull the model's JSON object out of raw text, tolerating stray fences/prose."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s.strip("`")
        if s.lstrip().startswith("json"):
            s = s.lstrip()[4:]
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found in model output")
    return json.loads(s[start:end + 1])


def _parse_and_validate(text: str) -> dict:
    """Extract the JSON object from a model's final message and sanity-check it."""
    analysis = _extract_json(text)
    if "regime" not in analysis:
        raise ValueError("analysis missing 'regime' key")
    return analysis


def _invoke_claude(prompt: str, model: str | None, cwd: str) -> dict:
    """One `claude -p` call. Prompt on stdin; result is a JSON wrapper on stdout."""
    proc = subprocess.run(
        ["claude", "-p", "--output-format", "json", "--model", model or "opus"],
        input=prompt, capture_output=True, text=True, cwd=cwd,
        timeout=config.REQUEST_TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude exited {proc.returncode}: {proc.stderr[:500]}")
    wrapper = json.loads(proc.stdout)
    if wrapper.get("is_error"):
        raise RuntimeError(f"claude reported error: {wrapper.get('result')}")
    return _parse_and_validate(wrapper.get("result", ""))


def _invoke_codex(prompt: str, model: str | None, cwd: str) -> dict:
    """One `codex exec` call. Prompt on stdin; final message captured to a file.

    Codex streams an event log to stdout, so we use --output-last-message to get
    just the agent's final message. read-only sandbox + skip-git-repo-check let it
    run non-interactively inside the throwaway cwd.
    """
    out_path = Path(cwd) / "codex_last_message.txt"
    if out_path.exists():
        out_path.unlink()
    cmd = ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check",
           "--cd", cwd, "--color", "never", "-o", str(out_path)]
    if model:
        cmd += ["-m", model]
    cmd += ["-"]  # read the prompt from stdin
    proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=cwd,
                          timeout=config.REQUEST_TIMEOUT_S)
    # Codex prints a banner first and the real error (e.g. usage limit) last, and
    # can exit 0 while still failing to produce output — so report the tail and
    # treat a missing file as failure regardless of exit code.
    tail = (proc.stderr or proc.stdout or "").strip()[-800:]
    if proc.returncode != 0:
        raise RuntimeError(f"codex exited {proc.returncode}: {tail}")
    if not out_path.exists():
        raise RuntimeError(f"codex produced no final-message file: {tail}")
    return _parse_and_validate(out_path.read_text())


# Maps each engine name in config.ENGINES to the function that invokes its CLI.
_RUNNERS = {"claude": _invoke_claude, "codex": _invoke_codex}


def run_engine(engine: str, prompt: str, model: str | None) -> dict:
    """Run one headless analysis via the chosen engine, with retries.

    The engine step is the only LLM touchpoint. Both runners execute from a
    throwaway cwd so the project's CLAUDE.md / AGENTS.md and skills never load
    into the isolated session. Retries on non-zero exit, timeout, or unparseable
    output.
    """
    invoke = _RUNNERS[engine]
    last_err: Exception | None = None
    with tempfile.TemporaryDirectory() as neutral_cwd:
        for attempt in range(1, config.MAX_ATTEMPTS + 1):
            log.info("%s analyze attempt %d/%d (model=%s)",
                     engine, attempt, config.MAX_ATTEMPTS, model or "engine default")
            try:
                return invoke(prompt, model, neutral_cwd)
            except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError,
                    RuntimeError, OSError) as e:
                last_err = e
                log.warning("%s attempt %d failed: %s", engine, attempt, e)
                continue
    raise RuntimeError(
        f"{engine} analysis failed after {config.MAX_ATTEMPTS} attempts: {last_err}")


def _join(value) -> str:
    """Sheets cells are strings; flatten a list field into a readable string."""
    if isinstance(value, list):
        return " | ".join(str(v) for v in value)
    return str(value or "")


def analysis_to_rows(analysis: dict, date_str: str, window_start: str, window_end: str) -> list[dict]:
    """Expand one analysis JSON into the per-ticker rows (schema = config.ROW_COLUMNS)."""
    regime = _join(analysis.get("regime")).strip()
    signals = _join(analysis.get("signals")).strip()
    sector = _join(analysis.get("sector_focus")).strip()

    # sector_focus has no dedicated column; fold it into the MARKET row's signal
    # cell (which backtest.py does not parse) so the information survives.
    market_signal = f"{signals}\n\nSector focus: {sector}" if sector else signals

    def _row(ticker, signal, play, invalidation):
        return dict(zip(ROW_COLUMNS, [
            date_str, ticker, regime, signal, play, invalidation,
            window_start, window_end,
        ]))

    rows = [_row("MARKET", market_signal, "", "")]
    for p in analysis.get("plays", []) or []:
        ticker = str(p.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        parts = [p.get("pattern"), p.get("structure"), p.get("thesis")]
        play_text = " | ".join(str(x).strip()
                               for x in parts if x and str(x).strip())
        trigger = str(p.get("trigger", "")).strip()
        if trigger:
            play_text = f"{play_text}. Trigger: {trigger}" if play_text else f"Trigger: {trigger}"
        confidence = str(p.get("confidence", "")).strip().lower()
        if confidence:
            play_text = f"[{confidence}] {play_text}" if play_text else f"[{confidence}]"
        rows.append(_row(ticker, "", play_text, str(
            p.get("invalidation", "")).strip()))
    return rows


def _warn_if_below_targets(analysis: dict) -> None:
    """Log a non-fatal warning when a run returns fewer plays than the contract asks for.

    Counts are by the play's `asset_class` tag; the run is never blocked — thin
    days legitimately yield fewer setups, so this is operator visibility only.
    """
    plays = analysis.get("plays") or []
    stocks = sum(1 for p in plays if str(p.get("asset_class", "")).strip().lower() == "stock")
    etfs = sum(1 for p in plays if str(p.get("asset_class", "")).strip().lower() == "etf")
    if stocks < config.MIN_STOCK_PLAYS or etfs < config.MIN_ETF_PLAYS:
        log.warning(
            "Play coverage below target: %d stock (want >=%d), %d ETF (want >=%d)",
            stocks, config.MIN_STOCK_PLAYS, etfs, config.MIN_ETF_PLAYS,
        )


def _dates_to_process(args, client) -> list[str]:
    """Resolve the invocation flags into an ordered list of trading dates."""
    if args.date:
        return [args.date]
    if args.start and args.end:
        d, last, out = date.fromisoformat(
            args.start), date.fromisoformat(args.end), []
        while d <= last:
            if d.weekday() < 5:
                out.append(d.isoformat())
            d += timedelta(days=1)
        return out
    latest = _latest_available_date(client)
    if not latest:
        log.error("No data available in Drive to analyze")
        return []
    return [latest]


def analyze_date(date_str: str, *, engine: str, model: str | None, tab: str,
                 days: int, top_n: int, framework_md: str, method_md: str,
                 write: bool) -> dict | None:
    """Run fetch → analyze → (write) for a single date. Returns the analysis dict."""
    log.info("Fetching data for %s (days=%d)", date_str, days)
    data_md = fetch_data(date_str=date_str, top_n=top_n, days=days)
    if "_No data available._" in data_md and data_md.count("_No data available._") >= 4:
        log.info("No data for %s — skipping", date_str)
        return None

    window = _last_n_trading_days(date_str, days)
    window_start, window_end = window[0], window[-1]

    prompt = build_prompt(framework_md, method_md, data_md, date_str)
    analysis = run_engine(engine, prompt, model)
    _warn_if_below_targets(analysis)

    rows = analysis_to_rows(analysis, date_str, window_start, window_end)
    if write:
        sheets_client.append_rows(tab, rows)
        log.info("Wrote %d row(s) for %s to %s", len(rows), date_str, tab)
    else:
        log.info("--dry-run: %d row(s) for %s NOT written to %s",
                 len(rows), date_str, tab)
    return analysis


def _print_report(date_str: str, analysis: dict, *, tab: str, written: bool) -> None:
    print(f"\n=== {date_str} ===")
    print(f"Regime: {_join(analysis.get('regime'))}")
    signals = _join(analysis.get("signals"))
    if signals:
        print(f"Signals: {signals}")
    plays = analysis.get("plays") or []
    if plays:
        print("Plays:")
        for p in plays:
            line = " | ".join(str(x) for x in [p.get(
                "ticker"), p.get("structure"), p.get("trigger")] if x)
            print(f"  - {line}")
    else:
        print("Plays: none")
    print(f"Written to {tab}: {'yes' if written else 'no (dry-run)'}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analysis_pipeline",
        description="Options flow analysis pipeline (fetch → headless claude/codex → Sheets).")
    parser.add_argument("--engine", choices=sorted(ENGINES), default=config.DEFAULT_ENGINE,
                        help="Analysis engine: claude (→ AnalysisClaude) or codex (→ AnalysisGPT). "
                             f"Default: {config.DEFAULT_ENGINE}.")
    parser.add_argument("--date", help="Single trading date YYYY-MM-DD.")
    parser.add_argument(
        "--start", help="Range start YYYY-MM-DD (use with --end).")
    parser.add_argument(
        "--end", help="Range end YYYY-MM-DD (use with --start).")
    parser.add_argument("--days", type=int, default=config.DEFAULT_DAYS,
                        help=f"Persistence window passed to the fetch step (default: {config.DEFAULT_DAYS}).")
    parser.add_argument("--top", type=int, default=config.DEFAULT_TOP_N,
                        help=f"Top-N raw trades per section (default: {config.DEFAULT_TOP_N}).")
    parser.add_argument("--model", default=None,
                        help="Model for the engine's headless call. Default: engine default "
                             "(claude→opus, codex→its configured model).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch + analyze but do not write to Sheets.")
    return parser


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    args = _build_parser().parse_args(argv)

    cfg = ENGINES[args.engine]
    model = args.model or cfg.default_model
    tab = cfg.tab
    framework_md = config.FRAMEWORK_FILE.read_text()
    method_md = cfg.method_file.read_text()
    log.info("Engine=%s model=%s tab=%s", args.engine,
             model or "engine default", tab)

    client = get_drive_client()
    dates = _dates_to_process(args, client)
    if not dates:
        sys.exit(1)
    log.info("Dates to process: %s", ", ".join(dates))

    analyzed, skipped = [], []
    for d in dates:
        try:
            analysis = analyze_date(
                d, engine=args.engine, model=model, tab=tab,
                days=args.days, top_n=args.top,
                framework_md=framework_md, method_md=method_md,
                write=not args.dry_run,
            )
        except Exception:
            log.exception("Analysis failed for %s", d)
            skipped.append(d)
            continue
        if analysis is None:
            skipped.append(d)
            continue
        analyzed.append(d)
        _print_report(d, analysis, tab=tab, written=not args.dry_run)

    print(f"\nAnalyzed: {', '.join(analyzed) or 'none'}")
    if skipped:
        print(f"Skipped:  {', '.join(skipped)}")
    if not analyzed:
        sys.exit(1)
