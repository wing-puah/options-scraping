"""
Core logic for the options flow analysis pipeline.

    fetch    → fetch.fetch_data                        (deterministic)
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
from .fetch import (
    _last_n_trading_days,
    _latest_available_date,
    fetch_data,
)
from lib.drive_client import get_drive_client
from lib import sheets_client
from lib.logger import setup_logging
import argparse
import csv
import json
import logging
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta
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


def build_prompt(framework_md: str, method_md: str, data_md: str, date_str: str,
                 focus_tickers: list[str] | None = None) -> str:
    """Assemble the full self-contained analysis prompt for the headless engine.

    When ``focus_tickers`` is set, the coverage section of the contract is
    overridden so the model returns plays only for those tickers.
    """
    contract = config.ANALYSIS_PROMPT_CONTRACT
    if focus_tickers:
        contract += "\n" + config.ANALYSIS_FOCUS_OVERRIDE.format(
            tickers=", ".join(t.upper() for t in focus_tickers))
    return "\n\n".join([
        "# Options flow analysis",
        "You are analyzing options flow data. Apply the method to the "
        "data and return the JSON described at the end. Work only from what is "
        "in this prompt — do not run commands or read files.",
        f"Date being analyzed: {date_str}",
        "## Method (judgment)\n\n" + method_md,
        "## Framework (vocabulary)\n\n" + _strip_output_section(framework_md),
        contract,
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
    """One `claude -p` call. Prompt on stdin; stdout is a JSON array of events."""
    proc = subprocess.run(
        ["claude", "-p", "--output-format", "json", "--model", model or config.ENGINES["claude"].default_model or "opus"],
        input=prompt, capture_output=True, text=True, cwd=cwd,
        timeout=config.REQUEST_TIMEOUT_S, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"claude exited {proc.returncode}: {proc.stderr[:500]}")
    parsed = json.loads(proc.stdout)
    # New Claude CLI emits a JSON array of events; find the result entry.
    if isinstance(parsed, list):
        result_events = [e for e in parsed if isinstance(e, dict) and e.get("type") == "result"]
        wrapper = result_events[-1] if result_events else {}
    else:
        wrapper = parsed
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
                          timeout=config.REQUEST_TIMEOUT_S, check=False)
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
    cfg = config.ENGINES.get(engine)
    last_err: Exception | None = None
    with tempfile.TemporaryDirectory() as neutral_cwd:
        for attempt in range(1, config.MAX_ATTEMPTS + 1):
            # On retries, drop to fallback_model if the caller didn't pin a model.
            effective_model = model
            if effective_model is None and attempt > 1 and cfg and cfg.fallback_model:
                effective_model = cfg.fallback_model
            log.info("%s analyze attempt %d/%d (model=%s)",
                     engine, attempt, config.MAX_ATTEMPTS, effective_model or "engine default")
            try:
                return invoke(prompt, effective_model, neutral_cwd)
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


def _multiline_signal(value) -> str:
    """Format the pipe-separated tagged-evidence signal onto multiple lines.

    The model returns signals like '[FLOW] x | [FLOW] y | [PRICE] z' — readable
    as a stream but cramped in a Sheets cell. One tag per line is much easier to
    scan when sheet wrap is on.
    """
    joined = _join(value).strip()
    if not joined:
        return ""
    parts = [p.strip() for p in joined.split("|")]
    return "\n".join(p for p in parts if p)


def _load_rollup_metrics(audit_path: Path) -> dict[str, dict]:
    """Read a date's scored-rollup CSV → ``{SYMBOL: {oi_confirm_pct, cpir, iv_spread, iv_skew, iv_pct}}``.

    The rollup is written by the fetch step at ``audit/<date>-rollup.csv`` before
    this runs, so the metrics are available to join onto the play rows. Returns
    ``{}`` when the file is missing (e.g. a fetch that wrote no audit). One row per
    ticker per section (stocks/etfs); keyed by upper-cased ``Symbol``."""
    if not audit_path.exists():
        return {}
    out: dict[str, dict] = {}
    with audit_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sym = (row.get("Symbol") or "").strip().upper()
            if not sym:
                continue
            out[sym] = {k: (row.get(col) or "").strip()
                        for k, col in config.ROLLUP_METRIC_COLS.items()}
    return out


def _score_cells(score: object) -> dict:
    """Turn a play's ``score`` object ({flow,dealer,price,vol,catalyst} points)
    into the sheet cells score_flow…score_catalyst + score_total (summed here,
    never trusted to the model). Missing/non-numeric components → blank; the total
    is the sum of whichever components are present (blank if none)."""
    obj = score if isinstance(score, dict) else {}

    def _int(v):
        try:
            return int(round(float(v)))
        except (TypeError, ValueError):
            return None

    comps = {col: _int(obj.get(key)) for col, key in config.SCORE_COMPONENT_COLS.items()}
    present = [v for v in comps.values() if v is not None]
    cells = {"score_total": sum(present) if present else ""}
    cells.update({col: (v if v is not None else "") for col, v in comps.items()})
    return cells


def _format_themes(themes: object) -> str:
    """Render the market-level ``themes`` array into a labeled block for the
    MARKET row's signal cell. Returns "" when there is nothing to show. Breadth is
    shown as a plain count — it is deliberately NOT a score multiplier."""
    if not isinstance(themes, list):
        return ""
    lines: list[str] = []
    for t in themes:
        if not isinstance(t, dict):
            continue
        name = str(t.get("theme", "")).strip()
        if not name:
            continue
        tickers = t.get("tickers") or []
        if isinstance(tickers, str):
            tickers = [tickers]
        tickers_str = ", ".join(str(x).strip() for x in tickers if str(x).strip())
        breadth = str(t.get("breadth", "")).strip()
        read = str(t.get("read", "")).strip()
        head = f"{name} (breadth {breadth})" if breadth else name
        line = f"{head}: {tickers_str}" if tickers_str else head
        if read:
            line += f" — {read}"
        lines.append(f"  {line}")
    return "Themes:\n" + "\n".join(lines) if lines else ""


def analysis_to_rows(analysis: dict, date_str: str, window_start: str, window_end: str,
                     rollup_metrics: dict[str, dict] | None = None) -> list[dict]:
    """Expand one analysis JSON into the per-ticker rows (schema = config.ROW_COLUMNS).

    INVARIANT — do not regress (fixed June 2026):
      - The MARKET row carries the top-level `regime` and `signals` (+ folded
        sector_focus).
      - Each play row carries its OWN `regime` and `signal` from inside the play
        dict — NOT the market-level fields. Either may be empty.
      - Never replace `p.get("regime")` / `p.get("signal")` with `market_regime`
        / `market_signal` (or hardcoded "") as a "simplification" — that
        collapses ticker-specific evidence into a duplicated market read, which
        is the exact regression this guards against.
    """
    market_regime = _join(analysis.get("regime")).strip()
    market_signal = _multiline_signal(analysis.get("signals"))
    sector = _join(analysis.get("sector_focus")).strip()

    # sector_focus has no dedicated column; fold it into the MARKET row's signal
    # cell (which backtest.py does not parse) so the information survives.
    if sector:
        market_signal = f"{market_signal}\n\nSector focus: {sector}" if market_signal else f"Sector focus: {sector}"

    # themes has no dedicated column either; fold the market-level thematic
    # breakdown into the MARKET row's signal cell the same way. Presentation only
    # — breadth is a count of independent names, never a score multiplier.
    themes_text = _format_themes(analysis.get("themes"))
    if themes_text:
        market_signal = f"{market_signal}\n\n{themes_text}" if market_signal else themes_text

    created_datetime = datetime.now().isoformat(timespec="seconds")
    rollup_metrics = rollup_metrics or {}

    def _row(ticker, regime, signal, play, trigger, invalidation,
             horizon="", metrics=None, scores=None):
        m = metrics or {}
        s = scores or {}
        return dict(zip(ROW_COLUMNS, [
            date_str, ticker, regime, signal, play, horizon, trigger, invalidation,
            window_start, window_end, created_datetime,
            # Deterministic per-ticker rollup context (blank on the MARKET row —
            # these are per-name flow metrics, not a market-level read).
            m.get("oi_confirm_pct", ""), m.get("cpir", ""), m.get("iv_spread", ""), m.get("iv_skew", ""),
            m.get("iv_pct", ""),
            # Model evidence-quality score, component breakdown + summed total
            # (blank on the MARKET row and whenever the play omits `score`).
            s.get("score_total", ""), s.get("score_flow", ""), s.get("score_dealer", ""),
            s.get("score_price", ""), s.get("score_vol", ""), s.get("score_catalyst", ""),
        ]))

    rows = [_row("MARKET", market_regime, market_signal, "", "", "")]
    for p in analysis.get("plays", []) or []:
        ticker = str(p.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        # Build the play cell as labeled lines so each part is scannable in Sheets.
        # First line: [flow_intent] — the intent classification, upper-cased. The
        # numeric score (component breakdown) and horizon now have their OWN sheet
        # columns, so they no longer clutter the bracket (and the backtest reads
        # horizon off its column instead of regex-scraping this line).
        play_lines: list[str] = []
        flow_intent = str(p.get("flow_intent", "")).strip().upper()
        if flow_intent:
            play_lines.append(f"[{flow_intent}]")
        headline_parts = [str(p.get(k, "")).strip() for k in ("pattern", "structure", "thesis")]
        headline = " | ".join(x for x in headline_parts if x)
        if headline:
            play_lines.append(headline)
        # `trigger` now has its own sheet column (after `play`), so it is no longer
        # folded into the play cell — only the Alt line stays inline.
        alt = str(p.get("alternative_interpretation", "")).strip()
        if alt:
            play_lines.append(f"Alt: {alt}")
        play_text = "\n".join(play_lines)
        trigger = str(p.get("trigger", "")).strip()
        horizon = str(p.get("horizon", "")).strip()
        scores = _score_cells(p.get("score"))
        play_regime = _join(p.get("regime")).strip()
        play_signal = _multiline_signal(p.get("signal"))
        rows.append(_row(ticker, play_regime, play_signal, play_text, trigger,
                         str(p.get("invalidation", "")).strip(), horizon=horizon,
                         metrics=rollup_metrics.get(ticker, {}), scores=scores))
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
                 days: int, top_n: int, raw_n: int, framework_md: str, method_md: str,
                 write: bool, focus_tickers: list[str] | None = None) -> dict | None:
    """Run fetch → analyze → (write) for a single date. Returns the analysis dict.

    ``focus_tickers`` narrows the per-ticker flow tables and the play coverage to
    those names (callers route the write to config.TICKER_SPECIFIC_TAB via `tab`).
    """
    log.info("Fetching data for %s (days=%d)", date_str, days)
    audit_path = config.ROOT / "audit" / f"{date_str}-rollup.csv"
    data_md = fetch_data(
        date_str=date_str, top_n=top_n, raw_n=raw_n, days=days,
        focus_tickers=focus_tickers, audit_csv_path=audit_path,
    )
    if "_No data available._" in data_md and data_md.count("_No data available._") >= 4:
        log.info("No data for %s — skipping", date_str)
        return None

    window = _last_n_trading_days(date_str, days)
    window_start, window_end = window[0], window[-1]

    prompt = build_prompt(framework_md, method_md, data_md, date_str, focus_tickers)
    analysis = run_engine(engine, prompt, model)
    _warn_if_below_targets(analysis)

    rows = analysis_to_rows(analysis, date_str, window_start, window_end,
                            rollup_metrics=_load_rollup_metrics(audit_path))
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
    parser.add_argument("--tickers",
                        help="Comma-separated symbols (e.g. NVDA,AMD,SPY) for a ticker-focused "
                             "run: narrows the per-ticker flow tables and returns plays only for "
                             f"these names. Writes to the {config.TICKER_SPECIFIC_TAB} tab "
                             "instead of the engine's daily tab. Full market context is retained.")
    parser.add_argument(
        "--start", help="Range start YYYY-MM-DD (use with --end).")
    parser.add_argument(
        "--end", help="Range end YYYY-MM-DD (use with --start).")
    parser.add_argument("--days", type=int, default=config.DEFAULT_DAYS,
                        help=f"Persistence window passed to the fetch step (default: {config.DEFAULT_DAYS}).")
    parser.add_argument("--top", type=int, default=config.DEFAULT_TOP_N,
                        help=f"Top-N tickers in rollup per flow section (default: {config.DEFAULT_TOP_N}).")
    parser.add_argument("--raw", type=int, default=config.DEFAULT_RAW_N,
                        help=f"Top-N raw trades per flow section (default: {config.DEFAULT_RAW_N}).")
    parser.add_argument("--model", default=None,
                        help="Model for the engine's headless call. Default: engine default "
                             "(claude→opus, codex→its configured model).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch + analyze but do not write to Sheets.")
    parser.add_argument("--skip-llm", action="store_true",
                        help="Fetch data and write audit CSV only — skip LLM analysis entirely. "
                             "Prints the prepared markdown to stdout.")
    return parser


def main(argv: list[str] | None = None) -> None:
    setup_logging()
    args = _build_parser().parse_args(argv)

    cfg = ENGINES[args.engine]
    model = args.model or cfg.default_model
    focus_tickers = [t.strip() for t in args.tickers.split(",") if t.strip()] if args.tickers else None
    # Ticker-focused runs route to a dedicated tab so they don't mix with the
    # full-market daily runs that backtest.py / `/options summary` read.
    tab = config.TICKER_SPECIFIC_TAB if focus_tickers else cfg.tab
    framework_md = ""
    method_md = ""
    if not args.skip_llm:
        framework_md = config.FRAMEWORK_FILE.read_text()
        method_md = cfg.method_file.read_text()
        log.info("Engine=%s model=%s tab=%s", args.engine, model or "engine default", tab)
        if focus_tickers:
            log.info("Ticker-focused run: %s → %s", ", ".join(focus_tickers), tab)

    client = get_drive_client()
    dates = _dates_to_process(args, client)
    if not dates:
        sys.exit(1)
    log.info("Dates to process: %s", ", ".join(dates))

    done, skipped = [], []
    for d in dates:
        audit_path = config.ROOT / "audit" / f"{d}-rollup.csv"
        try:
            data_md = fetch_data(
                date_str=d, top_n=args.top, raw_n=args.raw, days=args.days,
                focus_tickers=focus_tickers, audit_csv_path=audit_path,
            )
        except Exception:
            log.exception("Fetch failed for %s", d)
            skipped.append(d)
            continue

        if "_No data available._" in data_md and data_md.count("_No data available._") >= 4:
            log.info("No data for %s — skipping", d)
            skipped.append(d)
            continue

        if args.skip_llm:
            print(f"\n{'='*60}\n=== {d} — fetched data (audit: {audit_path}) ===\n{'='*60}\n")
            print(data_md)
            done.append(d)
            continue

        window = _last_n_trading_days(d, args.days)
        window_start, window_end = window[0], window[-1]
        try:
            prompt = build_prompt(framework_md, method_md, data_md, d, focus_tickers)
            analysis = run_engine(args.engine, prompt, model)
        except Exception:
            log.exception("Analysis failed for %s", d)
            skipped.append(d)
            continue
        if not focus_tickers:  # coverage minimums don't apply to focused runs
            _warn_if_below_targets(analysis)
        rows = analysis_to_rows(analysis, d, window_start, window_end,
                                rollup_metrics=_load_rollup_metrics(audit_path))
        if not args.dry_run:
            sheets_client.append_rows(tab, rows)
            log.info("Wrote %d row(s) for %s to %s", len(rows), d, tab)
        else:
            log.info("--dry-run: %d row(s) for %s NOT written to %s", len(rows), d, tab)
        done.append(d)
        _print_report(d, analysis, tab=tab, written=not args.dry_run)

    label = "Fetched" if args.skip_llm else "Analyzed"
    print(f"\n{label}: {', '.join(done) or 'none'}")
    if skipped:
        print(f"Skipped:  {', '.join(skipped)}")
    if not done:
        sys.exit(1)
