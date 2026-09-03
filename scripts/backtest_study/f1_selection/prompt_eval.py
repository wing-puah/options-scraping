"""HARNESS scoring a CANDIDATE analysis prompt against the SHIPPED one.

PRE-REGISTERED 2026-09-02 in research/pre-registrations/f1_selection/prompt_eval.md
BEFORE this file was written. Read that file first; nothing here may drift from
it. This module registers a HARNESS, not a hypothesis about the market: it fixes
how a candidate prompt is scored so a v5 bump can rest on a number instead of a
hand-edit. **Nothing here ships a prompt.** MET makes a candidate eligible for a
v5 bump PROPOSAL; the bump is an operator decision and a tab rename.

Exactly two arms, and only the prompt text differs between them:

  PROD       config/prompts/analysis-framework.md + analysis-methods/claude.md
  CANDIDATE  a named, committed snapshot directory holding the same two files
             plus a CANDIDATE.md describing the change (refused without it)

Both arms run the real pipeline on real dates and are backtested under the
SHIPPED ladder, tier map, structure universe, sizing and exits. Sub-commands:

  dates       select a date set BY THE REGISTERED RULE (variance / backfill)
  variance    PROD × N repeats on the variance set -> the NOISE FLOOR
  run         PROD vs CANDIDATE on a date set -> the criteria vector + verdict
  accumulate  one new LIVE date for the CANDIDATE arm (PROD = the live export)
  draft       ask a headless model for a candidate diff; NOTHING is applied

--- Isolation (registration §"Isolation invariants") -------------------------
Neither half of a run may reach Google Sheets. `--output-dir` on the analysis
pipeline skips the Sheets append unconditionally, and every derived backtest
config carries `output.sheet_tab: null` AND `proxy.sheet_tab: null` (both keys
PRESENT — `proxy.py` defaults an absent `sheet_tab` to `BacktestProxy`). This
module refuses to start, and refuses again before every subprocess, if any argv
would carry `--tab`, if a derived config's `sheet_tab` is missing or non-null,
or if an `--output-dir` / `local_csv` resolves outside the run directory. Every
subprocess command line is printed and appended to `<run-dir>/commands.log`.

--- What this book IS (registration §"Known confounds") ----------------------
Each arm is loaded with the DOCUMENTED escape hatch
`load_book(..., check_era=False, min_dates=0)` on the run's OWN CSVs, through
`text_corpus.load_corpus`. That is correct and it is the only sanctioned way to
load a synthetic arm book: the arm's exports are a few dozen dates produced by
this harness, not a prompt-version population, so `era.detect_era` has nothing
true to say about them and the shared 30-date floor would refuse a run whose
whole job is the 25-date criterion below. It is an ARM-COMPARISON book, never a
population claim, and NO era-scoped conclusion may be drawn from it. The report
prints this inline on every run.

--- Cost ---------------------------------------------------------------------
Option-history scraping for candidate strikes goes to the SHARED
`backtests/option_history_cache/` exactly as production does; `--cache-only` is
deliberately NOT set on the derived configs, so a candidate that emits new
strikes costs scrape time. The report says so and records wall time, call count
and the model used.

R is quoted, never dollars: the two arms emit different plays, so contract
counts are not comparable. No annualised figure, Sharpe, or time-to-recover
anywhere.
"""
from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import json
import math
import random
import re
import shlex
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import date as _date
from datetime import datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest_study.lib import era as era_mod  # noqa: E402
from scripts.backtest_study.lib import protocol as P  # noqa: E402
from scripts.backtest_study.lib import text_corpus as TC  # noqa: E402
from scripts.backtest_study.lib.book import load_book  # noqa: E402

# The runner promotes -latest.txt on these codes instead of deleting it, and it
# finds this constant by AST parse — so it must stay a PLAIN SET LITERAL. A
# `frozenset(...)` call is invisible to `ast.literal_eval` and the refusal would
# be misfiled as a failure. {2, 3} are `lib/era.py`'s (thin era / era mismatch);
# {4, 5, 6} are this harness's own, below.
DESIGNED_REFUSAL_EXIT_CODES = {2, 3, 4, 5, 6}

EXIT_ISOLATION = 4       # an argv, config or path that could reach Sheets / escape the run dir
EXIT_MISSING_INPUT = 5   # a prerequisite the registration names is absent (candidate dir, variance set)
EXIT_STALE_RUN_DIR = 6   # the run dir already holds an arm's output; the proxy writer would eat it

# ── FROZEN by the pre-registration; may not be tuned after any result is seen ──
TOP_K = 3                    # top-3/day replay, k fixed at 3
MIN_DATES = 25               # criterion 7 — the standing date-level power floor
MATURITY_DAYS = 90           # date set (b) rule 1: matured windows only
BOOT_N = P.BOOT_N            # 10000
ALPHA = 0.05
BOOT_SEED = 20260902
SELECTION_SEED = 20260902    # the deterministic date-selection seed

DEFAULT_RUN_ROOT = ROOT / "backtests" / "prompt_eval"
DEFAULT_VARIANCE_DATES = DEFAULT_RUN_ROOT / "variance-dates.txt"
DEFAULT_BACKFILL_DATES = DEFAULT_RUN_ROOT / "backfill-dates.txt"
DRAFT_ROOT = ROOT / "backtests" / "prompt_drafts"

PROD_FRAMEWORK = ROOT / "config" / "prompts" / "analysis-framework.md"
PROD_METHOD = ROOT / "config" / "prompts" / "analysis-methods" / "claude.md"
BASE_CONFIG = ROOT / "config" / "backtest.yml"

# The two prompt files a candidate directory may carry, by their PROD names.
CANDIDATE_FILES = ("analysis-framework.md", "claude.md")

# Tier-VETO'd at intake (config/backtest.yml entry.structure_veto). A candidate
# that emits one has broken the intake contract — criterion 5.
LEAK_STRUCTURE = "bear_call_spread"

DRAFT_MODEL = "claude-opus-5"     # registration default for `draft`
ENGINE = "claude"


class Refusal(Exception):
    """A DESIGNED refusal — a non-zero exit that is the harness's correct status."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ── report plumbing ──────────────────────────────────────────────────────────

class Report:
    """Print to stdout (run.py tees it) AND keep the lines for `report.txt`."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, s: str = "") -> None:
        print(s, flush=True)
        self.lines.append(s)

    def hdr(self, t: str) -> None:
        self(f"\n{'=' * 78}\n{t}\n{'=' * 78}")

    def sub(self, t: str) -> None:
        self(f"\n--- {t} " + "-" * max(0, 72 - len(t)))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        print(f"\n  report -> {path}")


def _fmt(x, spec: str = "+.4f") -> str:
    if x is None:
        return "n/a"
    if isinstance(x, float) and math.isnan(x):
        return "nan"
    return format(x, spec)


def _clean(obj):
    """NaN -> None so `summary.json` is strict JSON a later reader can trust."""
    if isinstance(obj, float):
        return None if math.isnan(obj) else obj
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, Counter):
        return {str(k): v for k, v in obj.items()}
    if isinstance(obj, Path):
        return str(obj)
    return obj


# ── isolation guards ─────────────────────────────────────────────────────────

def forbid_tab(tokens) -> None:
    """Refuse any argv that would name a Sheets tab. Checked on THIS process's
    argv at startup and again on every subprocess command line."""
    for tok in tokens:
        t = str(tok)
        if t == "--tab" or t.startswith("--tab="):
            raise Refusal(EXIT_ISOLATION,
                          f"argv carries --tab ({t!r}). No arm of this harness may name a "
                          f"Sheets tab; the analysis source is a local rows CSV and the "
                          f"backtest destination is a local CSV.")


def _inside(path, root) -> bool:
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except (ValueError, OSError):
        return False


def require_inside(path, run_dir, what: str) -> None:
    if not _inside(path, run_dir):
        raise Refusal(EXIT_ISOLATION,
                      f"{what} resolves OUTSIDE the run directory:\n"
                      f"    path     {Path(path).resolve()}\n"
                      f"    run dir  {Path(run_dir).resolve()}\n"
                      f"  A prompt-evaluation run writes only inside its own run "
                      f"directory — an escape is how a candidate arm overwrites "
                      f"production output.")


def check_derived_config(cfg: dict, run_dir: Path, where: str = "derived config") -> None:
    """Both `sheet_tab` keys PRESENT and null, every path inside the run dir.

    Presence is load-bearing, not pedantry: `scripts/backtest/proxy.py` reads
    `proxy_cfg.get("sheet_tab", "BacktestProxy")`, so an ABSENT key writes the
    production tab.
    """
    for section in ("output", "proxy"):
        sub = cfg.get(section) or {}
        if "sheet_tab" not in sub:
            raise Refusal(EXIT_ISOLATION,
                          f"{where}: {section}.sheet_tab is ABSENT. It must be present and "
                          f"null — proxy.py defaults a missing key to 'BacktestProxy'.")
        if sub["sheet_tab"] is not None:
            raise Refusal(EXIT_ISOLATION,
                          f"{where}: {section}.sheet_tab is {sub['sheet_tab']!r}, not null. "
                          f"No arm of this harness may write Sheets.")
    checks = [
        ("analysis.csv", (cfg.get("analysis") or {}).get("csv")),
        ("output.local_csv", (cfg.get("output") or {}).get("local_csv")),
        ("proxy.local_csv", (cfg.get("proxy") or {}).get("local_csv")),
        ("proxy.results_source_csv", (cfg.get("proxy") or {}).get("results_source_csv")),
    ]
    for key, value in checks:
        if not value:
            raise Refusal(EXIT_ISOLATION, f"{where}: {key} is not set.")
        require_inside(value, run_dir, f"{where}: {key}")
    if (cfg.get("analysis") or {}).get("tab"):
        raise Refusal(EXIT_ISOLATION,
                      f"{where}: analysis.tab is still set. `analysis.csv` wins over it, but "
                      f"leaving the tab named in a local-only config invites a later hand-edit "
                      f"that reads Sheets.")


# ── subprocess plumbing ──────────────────────────────────────────────────────

def run_cmd(cmd: list[str], run_dir: Path, log_path: Path | None = None,
            label: str = "") -> None:
    """Run `cmd`, refusing first if it would carry `--tab`. Logged, always.

    Output goes to `log_path` rather than stdout: a single analysis call prints
    the whole assembled prompt, and tee-ing that into the study report would
    bury the numbers. The tail is printed on failure.
    """
    forbid_tab(cmd)
    line = " ".join(shlex.quote(str(c)) for c in cmd)
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "commands.log").open("a", encoding="utf-8") as fh:
        fh.write(f"{datetime.now().isoformat(timespec='seconds')}  {line}\n")
    print(f"  $ {line}", flush=True)
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    out = (proc.stdout or "") + (proc.stderr or "")
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(out, encoding="utf-8")
    if proc.returncode != 0:
        tail = "\n".join(out.splitlines()[-40:])
        raise RuntimeError(f"{label or cmd[0]} exited {proc.returncode}:\n{tail}")
    print(f"    ok ({time.time() - t0:.1f}s)", flush=True)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def short_sha(path: Path) -> str:
    return sha256_of(path)[:12]


# ── date-set selection (registration §"Date sets") ───────────────────────────

def read_dates_file(path: Path) -> list[str]:
    """One ISO date per line; `#` comments and blanks ignored."""
    path = Path(path)
    if not path.exists():
        raise Refusal(EXIT_MISSING_INPUT, f"date set not found: {path}")
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.append(line)
    if not out:
        raise Refusal(EXIT_MISSING_INPUT, f"date set is empty: {path}")
    return sorted(dict.fromkeys(out))


def regime_by_date(records: list[dict]) -> dict[str, str]:
    """MODEL regime direction per signal date — the stratifier.

    The market read is carried on every row of a date, so the modal non-null
    `model_dir` is that date's label; a date whose regime string names no
    direction is its own stratum ("UNKNOWN") rather than being dropped or
    guessed into one.
    """
    by: dict[str, Counter] = {}
    for r in records:
        by.setdefault(str(r["date"]), Counter())[r.get("model_dir") or "UNKNOWN"] += 1
    return {d: c.most_common(1)[0][0] for d, c in by.items()}


def allocate(counts: dict[str, int], n: int) -> dict[str, int]:
    """Largest-remainder allocation of `n` across strata, proportional to
    `counts` and capped at each stratum's size. Deterministic: ties break on the
    stratum name, never on dict order."""
    total = sum(counts.values())
    if total == 0 or n <= 0:
        return {k: 0 for k in counts}
    n = min(n, total)
    quota = {k: n * v / total for k, v in counts.items()}
    alloc = {k: min(counts[k], int(quota[k])) for k in counts}
    while sum(alloc.values()) < n:
        cands = [k for k in counts if alloc[k] < counts[k]]
        if not cands:
            break
        cands.sort(key=lambda k: (-(quota[k] - alloc[k]), k))
        alloc[cands[0]] += 1
    return alloc


def select_dates(records: list[dict], n: int, as_of: _date, exclude: set[str],
                 seed: int = SELECTION_SEED) -> tuple[list[str], list[dict]]:
    """The registered rule, and no other:

      1. matured windows only — signal date <= as_of - MATURITY_DAYS
      2. stratified across MODEL REGIME x CALENDAR YEAR, proportional to the
         eligible population
      3. no date from the excluded (variance) set
      4. deterministic seed

    Returns `(dates, strata_table)`.
    """
    cutoff = (as_of - timedelta(days=MATURITY_DAYS)).isoformat()
    regimes = regime_by_date(records)
    eligible = sorted(d for d in regimes if d <= cutoff and d not in exclude)

    strata: dict[str, list[str]] = {}
    for d in eligible:
        strata.setdefault(f"{regimes[d]}x{d[:4]}", []).append(d)
    counts = {k: len(v) for k, v in strata.items()}
    alloc = allocate(counts, n)

    picked: list[str] = []
    table: list[dict] = []
    for stratum in sorted(strata):
        pool = sorted(strata[stratum])
        k = alloc.get(stratum, 0)
        # Seeded per STRATUM so adding a stratum (a new year, a new regime)
        # cannot reshuffle the dates already drawn from the others.
        rng = random.Random(f"{seed}|{stratum}")
        chosen = sorted(rng.sample(pool, k)) if k else []
        picked.extend(chosen)
        table.append(dict(stratum=stratum, eligible=len(pool), allocated=k,
                          selected=chosen))
    return sorted(picked), table


def write_dates_file(path: Path, dates: list[str], meta: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# prompt_eval date set — selected BY RULE, part of the run record.",
             "# research/pre-registrations/f1_selection/prompt_eval.md §'Date sets'"]
    for k, v in meta.items():
        lines.append(f"#   {k}: {v}")
    lines.extend(dates)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_dates(args) -> int:
    rep = Report()
    as_of = _date.fromisoformat(args.as_of) if args.as_of else _date.today()

    # The CURRENT-era book, era-checked: unlike the arm books below, this IS a
    # population question ("which of the era's dates are eligible"), so the era
    # guard and the shared floor both stay on.
    records, diag = load_book(include_bs=False)

    exclude: set[str] = set()
    if args.rule == "backfill":
        exc_path = Path(args.exclude) if args.exclude else DEFAULT_VARIANCE_DATES
        if not Path(exc_path).exists():
            raise Refusal(
                EXIT_MISSING_INPUT,
                f"the VARIANCE set is declared FIRST and run FIRST (registration §(a)); "
                f"no variance date file at {exc_path}.\n"
                f"  Run:  python -m scripts.backtest_study run prompt_eval -- dates "
                f"--rule variance --n 5 --out {DEFAULT_VARIANCE_DATES}")
        exclude = set(read_dates_file(exc_path))
    elif args.exclude:
        exclude = set(read_dates_file(args.exclude))

    dates, table = select_dates(records, args.n, as_of, exclude)

    rep.hdr(f"DATE SET — rule={args.rule}  n_requested={args.n}")
    rep(f"  era              {diag['era']}  ({diag['n_dates']} dates, "
        f"{diag['date_range'][0]} .. {diag['date_range'][1]})")
    rep(f"  as-of            {as_of}")
    rep(f"  maturity cutoff  {(as_of - timedelta(days=MATURITY_DAYS)).isoformat()} "
        f"(signal date <= as-of - {MATURITY_DAYS} d)")
    rep(f"  excluded         {len(exclude)} date(s)"
        + (f" from {args.exclude or DEFAULT_VARIANCE_DATES}" if exclude else ""))
    rep(f"  seed             {SELECTION_SEED} (per-stratum, deterministic)")

    rep.sub("STRATA — model regime x calendar year, proportional to the eligible population")
    rep(f"  {'stratum':<16} {'eligible':>8} {'allocated':>9}   dates")
    for row in table:
        rep(f"  {row['stratum']:<16} {row['eligible']:>8} {row['allocated']:>9}   "
            + (", ".join(row["selected"]) if row["selected"] else "-"))
    rep(f"  {'TOTAL':<16} {sum(r['eligible'] for r in table):>8} "
        f"{sum(r['allocated'] for r in table):>9}")

    out = Path(args.out)
    write_dates_file(out, dates, dict(
        rule=args.rule, n_requested=args.n, n_selected=len(dates),
        as_of=as_of.isoformat(), era=diag["era"], seed=SELECTION_SEED,
        maturity_days=MATURITY_DAYS,
        excluded=len(exclude),
        generated=datetime.now().isoformat(timespec="seconds")))
    rep(f"\n  {len(dates)} dates -> {out}")
    if args.rule == "backfill" and len(dates) < MIN_DATES:
        rep(f"\n  NOTE: {len(dates)} < the {MIN_DATES}-date floor (criterion 7). A run on "
            f"this set can only be UNDERPOWERED.")
    return 0


# ── one arm: analysis -> derived config -> backtest -> book ──────────────────

def arm_dir(run_dir: Path, arm: str, repeat: int | None = None) -> Path:
    return Path(run_dir) / (arm if repeat is None else f"{arm}-r{repeat}")


def arm_paths(adir: Path) -> dict[str, Path]:
    """The three CSVs an arm is read from. Named explicitly rather than derived
    at each call site because the LIVE set's PROD arm is the era EXPORT, not a
    directory this harness wrote."""
    adir = Path(adir)
    return {"analysis": adir / "analysis.csv", "results": adir / "results.csv",
            "proxy": adir / "proxy_results.csv"}


def candidate_prompts(candidate: Path) -> dict[str, Path]:
    """`{"framework": path|None, "method": path|None}` for a candidate dir.

    Refuses a directory with no CANDIDATE.md (the registration makes the diff
    and its rationale part of the record) or with neither prompt file.
    """
    candidate = Path(candidate)
    if not candidate.is_dir():
        raise Refusal(EXIT_MISSING_INPUT, f"candidate directory not found: {candidate}")
    if not (candidate / "CANDIDATE.md").exists():
        raise Refusal(
            EXIT_MISSING_INPUT,
            f"{candidate}/CANDIDATE.md is missing.\n"
            f"  A candidate is a NAMED, COMMITTED snapshot whose change is part of the "
            f"record (registration §Arms). Write CANDIDATE.md describing what changed and "
            f"why before scoring it.")
    framework = candidate / "analysis-framework.md"
    method = candidate / "claude.md"
    out = {"framework": framework if framework.exists() else None,
           "method": method if method.exists() else None}
    if out["framework"] is None and out["method"] is None:
        raise Refusal(
            EXIT_MISSING_INPUT,
            f"{candidate} holds neither analysis-framework.md nor claude.md — there is "
            f"nothing to score. A candidate that differs from PROD in no prompt file is "
            f"the PROD arm.")
    return out


def analysis_cmd(date_str: str, out_dir: Path, framework: Path | None,
                 method: Path | None, model: str | None,
                 skip_llm: bool = False) -> list[str]:
    cmd = [sys.executable, "-u", "-m", "scripts.analysis_pipeline",
           "--date", date_str, "--output-dir", str(out_dir)]
    if framework is not None:
        cmd += ["--framework-file", str(framework)]
    if method is not None:
        cmd += ["--method-file", str(method)]
    if model:
        cmd += ["--model", model]
    if skip_llm:
        cmd += ["--skip-llm"]
    return cmd


def run_analysis(dates: list[str], adir: Path, run_dir: Path, framework, method,
                 model: str | None, force: bool = False) -> int:
    """One `analysis_pipeline --output-dir` call per date. Resumable: a date
    whose `<date>-rows.csv` already exists is skipped unless `--force`, so a
    five-hour run that dies at hour four does not start over."""
    out_dir = adir / "analysis"
    require_inside(out_dir, run_dir, "--output-dir")
    out_dir.mkdir(parents=True, exist_ok=True)
    calls = 0
    for d in dates:
        if not force and (out_dir / f"{d}-rows.csv").exists():
            print(f"  = {d} already present, skipping (--force to redo)")
            continue
        run_cmd(analysis_cmd(d, out_dir, framework, method, model),
                run_dir, log_path=adir / "logs" / f"analysis-{d}.log",
                label=f"analysis_pipeline {d}")
        calls += 1
    return calls


def concat_rows(adir: Path) -> Path:
    """`<arm>/analysis.csv` — the arm's `<date>-rows.csv` files concatenated in
    ROW_COLUMNS order (every file carries the same header)."""
    out = adir / "analysis.csv"
    files = sorted((adir / "analysis").glob("*-rows.csv"))
    if not files:
        raise RuntimeError(f"no <date>-rows.csv under {adir / 'analysis'} — "
                           f"did every analysis call return plays?")
    header: list[str] | None = None
    rows: list[dict] = []
    for f in files:
        with f.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if header is None:
                header = list(reader.fieldnames or [])
            rows.extend(dict(r) for r in reader)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=header or [], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    return out


def derive_config(adir: Path, run_dir: Path, base_config: Path = BASE_CONFIG) -> Path:
    """`<arm>/backtest.yml` — `config/backtest.yml` loaded, with the six
    local-only keys set into the arm dir and NOTHING else changed.

    `--cache-only` is deliberately NOT set anywhere: candidate strikes that are
    not already in `backtests/option_history_cache/` are scraped exactly as
    production scrapes them, which is the honest pricing basis and is also the
    run's dominant wall-clock cost.
    """
    cfg = yaml.safe_load(Path(base_config).read_text(encoding="utf-8"))
    cfg.setdefault("analysis", {})
    cfg["analysis"].pop("tab", None)
    cfg["analysis"]["csv"] = str(adir / "analysis.csv")
    cfg.setdefault("output", {})
    cfg["output"]["local_csv"] = str(adir / "results.csv")
    cfg["output"]["sheet_tab"] = None
    cfg.setdefault("proxy", {})
    cfg["proxy"]["local_csv"] = str(adir / "proxy_results.csv")
    cfg["proxy"]["sheet_tab"] = None
    cfg["proxy"].pop("results_source_tab", None)
    cfg["proxy"]["results_source_csv"] = str(adir / "results.csv")

    check_derived_config(cfg, run_dir, where=f"{adir.name}/backtest.yml")

    path = adir / "backtest.yml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False),
                    encoding="utf-8")
    return path


def run_backtest(cfg_path: Path, adir: Path, run_dir: Path, force: bool = False) -> None:
    """`scripts.backtest` then `scripts.backtest.proxy` on the derived config.

    The proxy writer REPLACES (and archives) its local CSV per run and reads its
    "already evaluated" set FROM that same file when `sheet_tab` is null, so a
    second proxy pass into a used arm dir would evaluate only the new plays and
    then rename the complete file away. Each harness run therefore takes a FRESH
    run directory; a stale proxy CSV is refused rather than worked around.
    """
    proxy_csv = adir / "proxy_results.csv"
    if proxy_csv.exists() and not force:
        raise Refusal(
            EXIT_STALE_RUN_DIR,
            f"{proxy_csv} already exists.\n"
            f"  The proxy writer archives its local CSV and takes its idempotency set from "
            f"it, so re-running into a used arm directory silently truncates the book. Use "
            f"a FRESH --run-dir (the intended workflow), or --force to discard this one.")
    if force:
        proxy_csv.unlink(missing_ok=True)
        (adir / "results.csv").unlink(missing_ok=True)
    run_cmd([sys.executable, "-u", "-m", "scripts.backtest", "--config", str(cfg_path)],
            run_dir, log_path=adir / "logs" / "backtest.log", label="backtest")
    run_cmd([sys.executable, "-u", "-m", "scripts.backtest.proxy", "--config", str(cfg_path)],
            run_dir, log_path=adir / "logs" / "proxy.log", label="backtest.proxy")


def load_arm(adir: Path) -> tuple[list[dict], list[dict], dict]:
    """The arm's book, via the DOCUMENTED escape hatch.

    `check_era=False, min_dates=0` is the only sanctioned way to load a
    synthetic arm book (registration §"Known confounds"): these CSVs are this
    run's own output over a few dozen dates, not a prompt-version population, so
    `era.detect_era` has nothing true to say about them and the shared 30-date
    floor would refuse a run whose entire job is the 25-date criterion. It is an
    ARM-COMPARISON book; no era-scoped conclusion may be drawn from it.

    `require_proxy_calibration` keeps its default (gate SHUT) because this
    harness consumes STORED outcomes rather than re-replaying every row.
    """
    return TC.load_corpus(results_csv=adir / "results.csv",
                          proxy_csv=adir / "proxy_results.csv",
                          analysis_csv=adir / "analysis.csv",
                          include_bs=False, check_era=False, min_dates=0)


def score_arm(dates: list[str], adir: Path, run_dir: Path, framework, method,
              model: str | None, force: bool = False) -> dict:
    """Analysis -> concat -> derived config -> backtest -> book, for one arm."""
    adir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    calls = run_analysis(dates, adir, run_dir, framework, method, model, force=force)
    concat_rows(adir)
    cfg_path = derive_config(adir, run_dir)
    run_backtest(cfg_path, adir, run_dir, force=force)
    rows, unpriced, diag = load_arm(adir)
    return dict(name=adir.name, dir=adir, rows=rows, unpriced=unpriced, diag=diag,
                calls=calls, seconds=time.time() - t0, model=model,
                paths=arm_paths(adir))


# ── measures ─────────────────────────────────────────────────────────────────

def picks_of(rows: list[dict]) -> list[dict]:
    """The shipped ladder's top-3/day replay — the estimand's selection layer."""
    return P.top_k_per_day(rows, rank_fn=P.ladder_rank, k=TOP_K,
                           eligible_fn=P.ladder_eligible)


def mean_R_by_date(picks: list[dict]) -> dict[str, float]:
    by: dict[str, list[float]] = {}
    for p in picks:
        if p.get("R") is not None:
            by.setdefault(str(p["date"]), []).append(float(p["R"]))
    return {d: statistics.fmean(v) for d, v in by.items() if v}


def paired_by_date(picks_a: list[dict], picks_b: list[dict],
                   key_a: str = "a", key_b: str = "b") -> list[dict]:
    """One row per date carrying BOTH arms' mean R.

    The arms emit DIFFERENT plays, so rows cannot pair one-to-one; the DATE is
    the pairing unit, which is also the clustering unit every CI in
    `lib/protocol.py` resamples. Dates where either arm deployed nothing
    contribute nothing — the same-dates rule.
    """
    ma, mb = mean_R_by_date(picks_a), mean_R_by_date(picks_b)
    return [{"date": d, key_a: ma[d], key_b: mb[d]} for d in sorted(set(ma) & set(mb))]


def emissions_per_date(analysis_csv: Path, dates: set[str] | None = None) -> dict[str, int]:
    """Play rows the model EMITTED per date, straight off the arm's rows CSV —
    the count before the backtest could price anything.

    `dates` restricts the count, which the LIVE set needs: its PROD arm is the
    whole era export, and counting every date in it would compare a candidate's
    handful of live dates against three years of production.
    """
    path = Path(analysis_csv)
    out: Counter = Counter()
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            ticker = str(r.get("ticker") or "").strip().upper()
            d = str(r.get("date") or "")[:10]
            if ticker == "MARKET" or not str(r.get("play") or "").strip():
                continue
            if dates is not None and d not in dates:
                continue
            out[d] += 1
    return dict(out)


def leak_count(analysis_csv: Path, dates: set[str] | None = None) -> int:
    """`bear_call_spread` EMISSIONS in the arm's analysis rows.

    Counted by running the production classifier
    (`scripts.backtest.classify.classify_play`) over the play cells, NOT off a
    backtest export's `structure` column: the structure is VETO'd at intake, so
    a leak never reaches `BacktestResults` and lands in `BacktestProxy` as
    `skip_reason=vetoed` with the `structure` cell BLANK — a count keyed on that
    column reads every leak as zero, which is exactly the way criterion 5 could
    silently pass. Criterion 5 is about what the PROMPT emitted, so the analysis
    rows are the right population and the classifier is the right judge.

    `dates` restricts the count, which the LIVE set needs (its PROD arm is the
    whole era export).
    """
    from scripts.backtest.classify import classify_play  # noqa: PLC0415 - keeps
    # this research module importable without the backtest package's own imports.

    path = Path(analysis_csv)
    if not path.exists():
        return 0
    n = 0
    with path.open(newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            play = str(r.get("play") or "").strip()
            d = str(r.get("date") or "")[:10]
            if not play or str(r.get("ticker") or "").strip().upper() == "MARKET":
                continue
            if dates is not None and d not in dates:
                continue
            try:
                if classify_play(play).get("structure") == LEAK_STRUCTURE:
                    n += 1
            except Exception:  # noqa: BLE001 — an unparseable play is not a leak
                continue
    return n


def unpriceable_share(rows: list[dict], unpriced: list[dict]) -> tuple[float | None, Counter]:
    """Share of PLAY rows the backtest could not evaluate.

    A prompt that emits unpriceable structures buys its score with rows the
    backtest cannot see, so this prints beside every ΔR. `market_row` is not a
    play and is excluded from both sides.
    """
    reasons = Counter(u["reason"] for u in unpriced if u["reason"] != "market_row")
    n_unpriced = sum(reasons.values())
    denom = n_unpriced + len(rows)
    return ((n_unpriced / denom) if denom else None), reasons


def hallucination(rows: list[dict], cache_dir: Path = TC.CITATION_CACHE) -> dict:
    """`citation_check` aggregated over the arm's dates, with COVERAGE printed.

    The one network path in the whole measure set, and the one that is allowed
    to come back NOT EVALUABLE: it re-fetches each date's assembled analysis
    INPUT markdown through Drive, so a checkout with no credentials (or a date
    whose raws have been garbage-collected) yields no rate rather than a
    flattering zero.
    """
    try:
        out = TC.citations_for_rows(rows, cache_dir=cache_dir)
    except Exception as exc:  # noqa: BLE001 — an unmeasured rate, never a fake one
        return dict(evaluable=False, reason=str(exc)[:200], rate=None,
                    cited=0, found=0, dates=0, coverage=0.0)
    cited = sum(v["cited_n"] for v in out.values())
    found = sum(v["found_n"] for v in out.values())
    n_dates = len({str(r["date"])[:10] for r in rows})
    return dict(evaluable=True, reason=None,
                rate=(1 - found / cited) if cited else None,
                cited=cited, found=found, dates=len(out),
                coverage=(len(out) / n_dates) if n_dates else 0.0)


def read_variance_floor(run_dir: Path, explicit: Path | None = None) -> dict | None:
    """The floor from set (a). Looked for beside the run, then one level up —
    the variance set is computed once per (model, engine) pair and reprinted on
    every later run, so it normally lives in a sibling run directory."""
    candidates = [Path(explicit)] if explicit else [
        Path(run_dir) / "variance.json",
        Path(run_dir).parent / "variance.json",
        DEFAULT_RUN_ROOT / "variance.json",
    ]
    for path in candidates:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_path"] = str(path)
            return data
    return None


# ── the comparison + verdict ─────────────────────────────────────────────────

def current_era_label() -> str:
    """The era of the CURRENT to_evaluate exports, for the report header.

    Context only: the arm books below are this run's own CSVs and belong to no
    era (see `load_arm`). An unreadable or missing export is not an error here —
    the era of the live tab has no bearing on an arm comparison.
    """
    try:
        return era_mod.detect_era(era_mod.resolve_paths()["analysis"])
    except (OSError, ValueError):
        return "unresolved"


def verdict_of(c: dict, point: float, floor_established: bool) -> tuple[str, str]:
    """The registration's verdict grammar, and nothing else.

    Pure so the grammar is testable without a book. `c` is the criteria vector
    (True / False / None-for-not-evaluable); `point` is the paired ΔR.
    """
    powered = bool(c[7]) and floor_established
    if not powered:
        why = "criterion 7 fails" if not c[7] else "the variance floor is not established"
        return ("UNDERPOWERED",
                f"UNDERPOWERED — {why}. Census published above; nothing is read from it "
                f"and nothing is refuted.")
    if all(v is True for v in c.values()):
        return ("MET",
                "MET — all seven clear. The candidate is ELIGIBLE FOR A v5 BUMP PROPOSAL. "
                "It is NEVER a ship: the bump is an operator decision and a tab rename.")
    if c[1] and c[2] and point < 0:
        return ("CONTRARY",
                "CONTRARY — powered, the CI excludes zero, and the candidate is reliably "
                "WORSE. A real finding about the proposed edit; recorded, and the diff is "
                "kept with it.")
    if any(v is None for v in c.values()) and not any(v is False for v in c.values()):
        return ("NO PRE-REGISTERED VERDICT MATCHES",
                "NO PRE-REGISTERED VERDICT MATCHES — powered, nothing failed, but a "
                "criterion could not be evaluated. Resolved by hand in "
                "research/current.md, with these numbers.")
    return ("NOT MET",
            "NOT MET — powered, and the conjunction does not clear. Recorded; the "
            "candidate is NOT re-scored on these dates (a second run on the same set is "
            "criterion-shopping and is not permitted).")


def compare(rep: Report, prod: dict, cand: dict, floor: dict | None,
            date_set: str, skip_citations: bool = False) -> dict:
    """Every measure the registration names, computed identically on both arms,
    then the criteria vector and the verdict. Every measure is reported
    regardless of outcome."""
    arms = {"PROD": prod, "CAND": cand}
    picks = {k: picks_of(v["rows"]) for k, v in arms.items()}
    pairs = paired_by_date(picks["CAND"], picks["PROD"], "cand", "prod")
    n_dates = len(pairs)

    rep.hdr(f"ARM-COMPARISON BOOKS — {date_set} set")
    # The era header the registration asks for. `run.py` prepends its own
    # provenance header to the tee'd report; this line puts the same fact in the
    # run directory's own `report.txt`, which is read on its own.
    rep(f"  live-tab era (context only, NOT these books): {current_era_label()}")
    rep("  These are ARM-COMPARISON books loaded with the documented escape hatch")
    rep("  load_book(..., check_era=False, min_dates=0) on this run's OWN CSVs. They are")
    rep("  NOT a prompt-version population and NO era-scoped conclusion may be drawn")
    rep("  from them (registration §'Known confounds and hazards').")
    rep("")
    rep(f"  {'arm':<6} {'rows':>6} {'dates':>6} {'picks':>6} {'calls':>6} {'wall_s':>8}  dir")
    for k, v in arms.items():
        rep(f"  {k:<6} {len(v['rows']):>6} {v['diag']['n_dates']:>6} "
            f"{len(picks[k]):>6} {v['calls']:>6} {v['seconds']:>8.0f}  {Path(v['dir']).name}")

    rep.sub("PAIRED ΔR BY DATE — top-3/day replay under the shipped ladder")
    stats = {k: P.replay_stats(picks[k]) for k in arms}
    for k in arms:
        s = stats[k]
        rep(f"  {k:<6} n={s['n']:<5} dates={s['dates']:<5} mean R {_fmt(s['mean_R'])}  "
            f"win {_fmt(s['win'], '.1%')}")
    point = (statistics.fmean([p["cand"] for p in pairs])
             - statistics.fmean([p["prod"] for p in pairs])) if pairs else float("nan")
    lo, hi = (P.boot_ci_paired_by_date(pairs, "cand", "prod", n=BOOT_N, seed=BOOT_SEED,
                                       alpha=ALPHA) if pairs else (float("nan"), float("nan")))
    rep(f"  paired dates (both arms deployed): {n_dates}")
    rep(f"  Δ mean R (CAND - PROD) {_fmt(point)}   CI [{_fmt(lo)}, {_fmt(hi)}]  "
        f"(date-clustered, BOOT_N={BOOT_N}, α={ALPHA})")

    rep.sub("PAIRED PROFIT FACTOR — read BESIDE mean R, never alone")
    pf_point, pf_lo, pf_hi = P.pf_paired_by_date(picks["CAND"], picks["PROD"], key="R",
                                                 n=BOOT_N, seed=BOOT_SEED, alpha=ALPHA)
    for k in arms:
        rep(f"  PF({k}) {_fmt(P.pf(picks[k], 'R'), '.3f')}")
    rep(f"  PF(CAND) - PF(PROD) {_fmt(pf_point, '+.3f')}   CI [{_fmt(pf_lo, '+.3f')}, "
        f"{_fmt(pf_hi, '+.3f')}]")

    rep.sub("TIER-MIX CENSUS")
    rep(f"  {'arm':<6} {'A':>5} {'B':>5} {'C':>5} {'VETO':>5}   (all priced rows)")
    tier_mix = {}
    for k, v in arms.items():
        c = Counter(r["tier"] for r in v["rows"])
        tier_mix[k] = dict(c)
        rep(f"  {k:<6} {c['A']:>5} {c['B']:>5} {c['C']:>5} {c['VETO']:>5}")

    rep.sub("EMISSIONS PER DATE")
    emissions = {}
    for k, v in arms.items():
        per = emissions_per_date(v["paths"]["analysis"], v.get("date_filter"))
        emissions[k] = per
        vals = list(per.values())
        rep(f"  {k:<6} total {sum(vals):>5}  dates {len(vals):>4}  "
            f"mean/date {_fmt(statistics.fmean(vals) if vals else float('nan'), '.2f')}")

    rep.sub("UNPRICEABLE SHARE — a prompt must not buy its score with rows the backtest cannot see")
    unpr = {}
    for k, v in arms.items():
        share, reasons = unpriceable_share(v["rows"], v["unpriced"])
        unpr[k] = dict(share=share, reasons=dict(reasons))
        detail = "  ".join(f"{r}={n}" for r, n in reasons.most_common()) or "(none)"
        rep(f"  {k:<6} {_fmt(share, '.1%')}   {detail}")
    rep("  NOTE: candidate strikes not already in the shared option_history_cache are a")
    rep("  MECHANICAL reason for a higher candidate share — read this beside the ΔR.")

    rep.sub("CITATION CHECK — hallucination rate, with coverage")
    hall = {}
    for k, v in arms.items():
        if skip_citations:
            hall[k] = dict(evaluable=False, reason="--skip-citations", rate=None,
                           cited=0, found=0, dates=0, coverage=0.0)
        else:
            hall[k] = hallucination(v["rows"])
        h = hall[k]
        if not h["evaluable"]:
            rep(f"  {k:<6} NOT EVALUABLE — {h['reason']}")
        else:
            rep(f"  {k:<6} rate {_fmt(h['rate'], '.1%')}  cited={h['cited']} "
                f"found={h['found']}  coverage {h['coverage']:.0%} "
                f"({h['dates']} dates fetched)")

    rep.sub(f"{LEAK_STRUCTURE.upper()} LEAKS — MUST BE 0 (tier-VETO'd at intake)")
    leaks = {k: leak_count(v["paths"]["analysis"], v.get("date_filter"))
             for k, v in arms.items()}
    for k in arms:
        rep(f"  {k:<6} {leaks[k]}")

    rep.sub("VARIANCE FLOOR — set (a), reprinted on every report")
    if floor is None:
        rep("  NOT ESTABLISHED. No |ΔR| below an unmeasured floor may be called a")
        rep("  difference, so criterion 2 cannot pass and the verdict is UNDERPOWERED.")
        rep(f"  Establish it:  python -m scripts.backtest_study run prompt_eval -- variance "
            f"--dates {DEFAULT_VARIANCE_DATES} --repeats 3 --run-dir <dir>")
        floor_value = None
    else:
        floor_value = floor.get("floor")
        rep(f"  floor {_fmt(floor_value, '.4f')} (max |paired ΔR| between PROD repeats)  "
            f"model={floor.get('model')}  engine={floor.get('engine')}")
        rep(f"  from {floor.get('_path')}  ({floor.get('repeats')} repeats x "
            f"{len(floor.get('dates') or [])} dates)")
        rep("  BINDING: no |ΔR| smaller than this may be called a difference, here or in")
        rep("  any write-up that cites this run.")

    rep.sub("LEAVE-ONE-DATE-OUT — read min_gain, not the average")
    loo_mean, loo_share, loo_min, loo_n = (
        P.loo_by_date(pairs, lambda r: r["cand"], lambda r: r["prod"])
        if pairs else (float("nan"), float("nan"), float("nan"), 0))
    rep(f"  folds {loo_n}  mean gain {_fmt(loo_mean)}  share positive "
        f"{_fmt(loo_share, '.0%')}  min gain {_fmt(loo_min)}")

    # ── criteria ──
    ci_excludes_zero = bool(pairs) and not (lo <= 0 <= hi)
    c = {
        1: ci_excludes_zero,
        2: (None if floor_value is None else
            (bool(pairs) and abs(point) > float(floor_value))),
        3: (None if pf_point is None or math.isnan(pf_lo) else bool(pf_lo >= 0)),
        4: (None if not (hall["CAND"]["evaluable"] and hall["PROD"]["evaluable"])
            or hall["CAND"]["rate"] is None or hall["PROD"]["rate"] is None
            else bool(hall["CAND"]["rate"] <= hall["PROD"]["rate"])),
        5: bool(leaks["CAND"] == 0 and leaks["PROD"] == 0),
        6: (None if loo_n == 0 else bool(loo_share == 1.0)),
        7: bool(n_dates >= MIN_DATES),
    }
    labels = {
        1: f"paired ΔR CI excludes zero (CI [{_fmt(lo)}, {_fmt(hi)}])",
        2: f"|ΔR| > variance floor ({_fmt(abs(point) if pairs else float('nan'), '.4f')} vs "
           f"{_fmt(floor_value, '.4f')})",
        3: f"PF(cand) >= PF(prod) by CI (lo {_fmt(pf_lo, '+.3f')})",
        4: f"hallucination rate not worse ({_fmt(hall['CAND']['rate'], '.1%')} vs "
           f"{_fmt(hall['PROD']['rate'], '.1%')})",
        5: f"zero {LEAK_STRUCTURE} leaks (cand {leaks['CAND']}, prod {leaks['PROD']})",
        6: f"every LOO fold positive (share {_fmt(loo_share, '.0%')}, min {_fmt(loo_min)})",
        7: f">= {MIN_DATES} paired dates ({n_dates})",
    }

    rep.hdr("CRITERIA VECTOR (all seven, or it is not MET)")
    for i in sorted(c):
        mark = {True: "PASS", False: "FAIL", None: "NOT EVALUABLE"}[c[i]]
        rep(f"  {i}. [{mark:^13}] {labels[i]}")

    verdict, detail = verdict_of(c, point, floor_value is not None)

    rep.hdr(f"VERDICT ({date_set} set): {verdict}")
    rep(f"  {detail}")
    rep("")
    rep("  Precedence, fixed by the registration: a LIVE-set verdict SUPERSEDES the")
    rep("  BACKFILL verdict once the LIVE set reaches the 25-date floor. A backfill MET")
    rep("  plus a live NOT MET is NOT MET.")
    rep("  R is quoted, never dollars — the arms emit different plays, so contract counts")
    rep("  are not comparable. No annualised figure, Sharpe, or time-to-recover is printed.")

    return dict(
        date_set=date_set, verdict=verdict, criteria=c, criteria_labels=labels,
        n_paired_dates=n_dates, delta_mean_R=point, ci=[lo, hi],
        pf_delta=pf_point, pf_ci=[pf_lo, pf_hi],
        pf={k: P.pf(picks[k], "R") for k in arms},
        replay={k: stats[k] for k in arms},
        tier_mix=tier_mix, emissions={k: sum(v.values()) for k, v in emissions.items()},
        unpriceable=unpr, hallucination=hall, leaks=leaks,
        variance_floor=floor_value, variance_floor_path=(floor or {}).get("_path"),
        loo=dict(mean=loo_mean, share_positive=loo_share, min=loo_min, folds=loo_n),
        pairs=pairs,
    )


# ── sub-command: variance ────────────────────────────────────────────────────

def cmd_variance(args) -> int:
    rep = Report()
    run_dir = Path(args.run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    dates = read_dates_file(args.dates)
    model = args.model

    rep.hdr("VARIANCE SET (a) — the NOISE FLOOR, PROD arm only")
    rep(f"  dates    {len(dates)}: {', '.join(dates)}")
    rep(f"  repeats  {args.repeats}   ({len(dates) * args.repeats} model calls)")
    rep(f"  model    {model or 'engine default'}   engine {ENGINE}")
    rep(f"  PROD sha framework {short_sha(PROD_FRAMEWORK)}  method {short_sha(PROD_METHOD)}")
    rep("  `claude -p` exposes no temperature knob, so the within-arm spread is unknown")
    rep("  and unbounded until measured. Everything below is PROD against PROD.")

    arms = []
    for k in range(1, args.repeats + 1):
        rep.sub(f"repeat {k}/{args.repeats}")
        arms.append(score_arm(dates, arm_dir(run_dir, "prod", k), run_dir,
                              None, None, model, force=args.force))

    picks = [picks_of(a["rows"]) for a in arms]
    means = [mean_R_by_date(p) for p in picks]

    rep.sub("PER-DATE SPREAD of mean R across repeats")
    common = sorted(set.intersection(*[set(m) for m in means])) if means else []
    spreads = []
    rep(f"  {'date':<12} " + " ".join(f"r{k + 1:<8}" for k in range(len(arms))) + "   spread")
    for d in common:
        vals = [m[d] for m in means]
        spread = max(vals) - min(vals)
        spreads.append(spread)
        rep(f"  {d:<12} " + " ".join(f"{v:+8.4f} " for v in vals) + f"  {spread:.4f}")
    if spreads:
        rep(f"  mean spread {statistics.fmean(spreads):.4f}   max spread {max(spreads):.4f}   "
            f"({len(common)} dates common to every repeat)")
    else:
        rep("  no date is common to every repeat — the floor cannot be computed.")

    rep.sub("EMISSION COUNT / TIER MIX across repeats")
    em = [emissions_per_date(a["paths"]["analysis"]) for a in arms]
    for k, a in enumerate(arms):
        tiers = Counter(r["tier"] for r in a["rows"])
        rep(f"  r{k + 1}  emissions {sum(em[k].values()):>4}  rows {len(a['rows']):>4}  "
            f"tiers A={tiers['A']} B={tiers['B']} C={tiers['C']} VETO={tiers['VETO']}")
    em_spread = {}
    for d in sorted(set().union(*[set(e) for e in em]) if em else []):
        vals = [e.get(d, 0) for e in em]
        em_spread[d] = max(vals) - min(vals)
    if em_spread:
        rep(f"  emission-count spread per date: mean "
            f"{statistics.fmean(em_spread.values()):.2f}  max {max(em_spread.values())}")

    rep.sub("PAIRWISE PAIRED ΔR between PROD repeats — this IS the floor")
    per_pair = []
    for i in range(len(arms)):
        for j in range(i + 1, len(arms)):
            pairs = paired_by_date(picks[i], picks[j], "a", "b")
            if not pairs:
                rep(f"  r{i + 1} vs r{j + 1}: no common deployed date")
                continue
            point = (statistics.fmean([p["a"] for p in pairs])
                     - statistics.fmean([p["b"] for p in pairs]))
            lo, hi = P.boot_ci_paired_by_date(pairs, "a", "b", n=BOOT_N, seed=BOOT_SEED,
                                              alpha=ALPHA)
            per_pair.append(dict(a=i + 1, b=j + 1, dates=len(pairs), point=point,
                                 ci=[lo, hi]))
            rep(f"  r{i + 1} vs r{j + 1}: dates {len(pairs):<4} ΔR {point:+.4f}  "
                f"CI [{lo:+.4f}, {hi:+.4f}]")
    floor = max((abs(p["point"]) for p in per_pair), default=None)

    rep.hdr("VARIANCE FLOOR")
    if floor is None:
        rep("  NOT ESTABLISHED — no pair of repeats shares a deployed date.")
    else:
        rep(f"  floor = {floor:.4f}  (max |paired ΔR| over {len(per_pair)} PROD-vs-PROD pairs)")
        rep("  BINDING CONSEQUENCE: no |ΔR| smaller than this may be called a difference,")
        rep("  in this study or in any write-up that cites it.")
    rep("  The floor is estimated from 5 dates by design. It is a FLOOR, not a")
    rep("  distributional claim, and is re-estimated whenever the model or engine changes.")

    payload = _clean(dict(
        floor=floor, repeats=args.repeats, dates=dates, model=model, engine=ENGINE,
        prod_sha=dict(framework=sha256_of(PROD_FRAMEWORK), method=sha256_of(PROD_METHOD)),
        per_pair=per_pair,
        per_date_spread={d: (max(m[d] for m in means) - min(m[d] for m in means))
                         for d in common},
        emission_spread=em_spread,
        tier_mix=[dict(Counter(r["tier"] for r in a["rows"])) for a in arms],
        calls=sum(a["calls"] for a in arms),
        seconds=sum(a["seconds"] for a in arms),
        generated=datetime.now().isoformat(timespec="seconds"),
    ))
    out = run_dir / "variance.json"
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    rep(f"\n  variance.json -> {out}")
    rep(f"  model calls {payload['calls']}   wall {payload['seconds']:.0f}s")
    rep.save(run_dir / "report.txt")
    return 0


# ── sub-command: run ─────────────────────────────────────────────────────────

def write_manifest(run_dir: Path, args, dates: list[str], cand: dict[str, Path | None]) -> Path:
    """Model + framework/method sha256 + argv + timestamp, per the build notes."""
    entry = dict(
        generated=datetime.now().isoformat(timespec="seconds"),
        argv=sys.argv[1:],
        engine=ENGINE, model=args.model,
        dates=dates, n_dates=len(dates),
        prod=dict(framework=str(PROD_FRAMEWORK.relative_to(ROOT)),
                  framework_sha256=sha256_of(PROD_FRAMEWORK),
                  method=str(PROD_METHOD.relative_to(ROOT)),
                  method_sha256=sha256_of(PROD_METHOD)),
        candidate=dict(
            dir=str(args.candidate),
            framework_sha256=sha256_of(cand["framework"]) if cand["framework"] else None,
            method_sha256=sha256_of(cand["method"]) if cand["method"] else None,
            rationale_sha256=sha256_of(Path(args.candidate) / "CANDIDATE.md")),
    )
    path = Path(run_dir) / "manifest.json"
    path.write_text(json.dumps(entry, indent=2, sort_keys=True), encoding="utf-8")
    return path


def write_candidate_diff(run_dir: Path, cand: dict[str, Path | None]) -> Path:
    """The PROD->CANDIDATE diff, stored with the run: the registration makes it
    part of the record, and a CONTRARY verdict is kept together with it."""
    chunks = []
    for label, prod_path, cand_path in (
            ("analysis-framework.md", PROD_FRAMEWORK, cand["framework"]),
            ("claude.md", PROD_METHOD, cand["method"])):
        if cand_path is None:
            chunks.append(f"# {label}: unchanged (candidate carries no override)\n")
            continue
        chunks.extend(difflib.unified_diff(
            prod_path.read_text(encoding="utf-8").splitlines(keepends=True),
            Path(cand_path).read_text(encoding="utf-8").splitlines(keepends=True),
            fromfile=f"prod/{label}", tofile=f"cand/{label}"))
    path = Path(run_dir) / "candidate.diff"
    path.write_text("".join(chunks), encoding="utf-8")
    return path


def cmd_run(args) -> int:
    rep = Report()
    run_dir = Path(args.run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    dates = read_dates_file(args.dates)
    cand_files = candidate_prompts(args.candidate)
    manifest = write_manifest(run_dir, args, dates, cand_files)
    diff_path = write_candidate_diff(run_dir, cand_files)

    rep.hdr("PROMPT EVAL — PROD vs CANDIDATE")
    rep(f"  run dir    {run_dir}")
    rep(f"  dates      {len(dates)} from {args.dates}")
    rep(f"  model      {args.model or 'engine default'}   engine {ENGINE}")
    rep(f"  PROD       framework sha {short_sha(PROD_FRAMEWORK)}  "
        f"method sha {short_sha(PROD_METHOD)}")
    rep("             (a report whose PROD sha differs from the committed files at "
        "read time is VOID)")
    rep(f"  CANDIDATE  {args.candidate}")
    for key, path in cand_files.items():
        rep(f"             {key:<9} " + (f"{short_sha(path)}  {path}" if path
                                         else "(unchanged — PROD file used)"))
    rep(f"  manifest   {manifest}")
    rep(f"  diff       {diff_path}")
    rep("  Option-history scraping for candidate strikes goes to the SHARED")
    rep("  backtests/option_history_cache/ exactly as production does; --cache-only is NOT")
    rep("  set on the derived configs, so new strikes cost scrape time.")

    repeats = max(1, int(args.repeats))
    books = {}
    for arm, framework, method in (("prod", None, None),
                                   ("cand", cand_files["framework"], cand_files["method"])):
        for k in range(1, repeats + 1):
            adir = arm_dir(run_dir, arm, None if repeats == 1 else k)
            rep.sub(f"{arm} arm{'' if repeats == 1 else f' repeat {k}'}")
            books.setdefault(arm, []).append(
                score_arm(dates, adir, run_dir, framework, method, args.model,
                          force=args.force))

    if repeats > 1:
        rep.sub("SPREAD WITHIN EACH ARM across this run's own repeats "
                "(headline uses repeat 1)")
        for arm, arm_books in books.items():
            ms = [mean_R_by_date(picks_of(b["rows"])) for b in arm_books]
            common = sorted(set.intersection(*[set(m) for m in ms])) if ms else []
            sp = [max(m[d] for m in ms) - min(m[d] for m in ms) for d in common]
            rep(f"  {arm:<5} dates {len(common):<4} mean spread "
                f"{_fmt(statistics.fmean(sp) if sp else float('nan'), '.4f')}  "
                f"max {_fmt(max(sp) if sp else float('nan'), '.4f')}")

    floor = read_variance_floor(run_dir, Path(args.variance_json) if args.variance_json else None)
    summary = compare(rep, books["prod"][0], books["cand"][0], floor,
                      date_set=args.date_set, skip_citations=args.skip_citations)

    summary["run_dir"] = str(run_dir)
    summary["manifest"] = str(manifest)
    summary["candidate_diff"] = str(diff_path)
    summary["model"] = args.model
    summary["dates"] = dates
    summary["calls"] = sum(b["calls"] for arm in books.values() for b in arm)
    summary["seconds"] = sum(b["seconds"] for arm in books.values() for b in arm)
    rep(f"\n  model calls {summary['calls']}   wall {summary['seconds']:.0f}s   "
        f"model {args.model or 'engine default'}")
    (run_dir / "summary.json").write_text(
        json.dumps(_clean(summary), indent=2, sort_keys=True), encoding="utf-8")
    rep(f"  summary.json -> {run_dir / 'summary.json'}")
    rep.save(run_dir / "report.txt")
    return 0


# ── sub-command: accumulate ──────────────────────────────────────────────────

def cmd_accumulate(args) -> int:
    """CANDIDATE arm only for ONE new live date; PROD is the live tab's export.

    Production already produced the PROD arm that day, so the LIVE set costs one
    extra model call per day. This mode ACCUMULATES: the candidate arm's date
    directory grows, its whole book is re-priced from the accumulated rows CSV,
    and the PROD side is the CURRENT-ERA export restricted to the same dates.

    The pairing caveat, printed on every run: the PROD side is only as complete
    as the last production backtest + export. A live date whose PROD rows have
    not been backtested and re-exported yet simply does not pair, so the LIVE
    date count grows a step behind the candidate's.
    """
    rep = Report()
    run_dir = Path(args.run_dir).resolve()
    live_dir = run_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    cand_files = candidate_prompts(args.candidate)

    rep.hdr(f"ACCUMULATE — CANDIDATE arm, live date {args.date}")
    rep(f"  run dir    {run_dir}")
    rep(f"  CANDIDATE  {args.candidate}")
    rep("  PROD       the live tab's own export for these dates "
        "(backtests/to_evaluate/, era-checked)")

    cdir = live_dir / "cand"
    cdir.mkdir(parents=True, exist_ok=True)
    calls = run_analysis([args.date], cdir, run_dir, cand_files["framework"],
                         cand_files["method"], args.model, force=args.force)
    concat_rows(cdir)
    cfg_path = derive_config(cdir, run_dir)
    # The accumulated book is re-priced in full each time, so the proxy CSV from
    # the previous day is stale by construction: drop it rather than let the
    # proxy's idempotency set truncate the rewrite (see run_backtest).
    run_backtest(cfg_path, cdir, run_dir, force=True)
    cand_rows, cand_unpriced, cand_diag = load_arm(cdir)
    live_dates = sorted({str(r["date"])[:10] for r in cand_rows})

    rep.sub("CANDIDATE — accumulated")
    rep(f"  model calls this invocation: {calls}")
    rep(f"  rows {len(cand_rows)}  dates {len(live_dates)}: "
        f"{live_dates[0] if live_dates else '-'} .. {live_dates[-1] if live_dates else '-'}")

    # PROD side: the current-era export, era-checked (this one IS a population),
    # with the shared floor disabled because the LIVE set's own 25-date floor is
    # criterion 7 and is evaluated below.
    prod_rows, prod_unpriced, prod_diag = TC.load_corpus(include_bs=False, min_dates=0)
    prod_rows = [r for r in prod_rows if str(r["date"])[:10] in set(live_dates)]
    prod_dates = sorted({str(r["date"])[:10] for r in prod_rows})
    rep.sub("PROD — the live export, restricted to the accumulated live dates")
    rep(f"  era {prod_diag['era']}   rows {len(prod_rows)}  dates {len(prod_dates)}")
    missing = sorted(set(live_dates) - set(prod_dates))
    if missing:
        rep(f"  {len(missing)} live date(s) have no PROD rows yet — "
            f"{', '.join(missing[:8])}{' …' if len(missing) > 8 else ''}")
        rep("  CAVEAT: the PROD side is only as complete as the last production backtest +")
        rep("  export. Those dates do not pair and the LIVE count grows a step behind.")

    if not prod_dates:
        rep.hdr("VERDICT (LIVE set): UNDERPOWERED")
        rep("  No live date pairs with the PROD export yet — census only, nothing read.")
        rep.save(run_dir / "report.txt")
        return 0

    prod_unpriced = [u for u in prod_unpriced if str(u.get("date", ""))[:10] in set(live_dates)]
    era_paths = era_mod.resolve_paths()
    prod_arm = dict(name="prod-live", dir=era_paths["analysis"].parent, rows=prod_rows,
                    unpriced=prod_unpriced, diag=prod_diag, calls=0, seconds=0.0,
                    model=None,
                    paths={"analysis": era_paths["analysis"],
                           "results": era_paths["results"],
                           "proxy": era_paths["proxy"]},
                    date_filter=set(live_dates))
    cand_arm = dict(name="cand-live", dir=cdir, rows=cand_rows, unpriced=cand_unpriced,
                    diag=cand_diag, calls=calls, seconds=0.0, model=args.model,
                    paths=arm_paths(cdir))

    floor = read_variance_floor(run_dir,
                                Path(args.variance_json) if args.variance_json else None)
    summary = compare(rep, prod_arm, cand_arm, floor, date_set="LIVE",
                      skip_citations=args.skip_citations)
    summary["live_dates"] = live_dates
    summary["prod_dates"] = prod_dates
    summary["unpaired_dates"] = missing
    (run_dir / "summary.json").write_text(
        json.dumps(_clean(summary), indent=2, sort_keys=True), encoding="utf-8")
    rep(f"  summary.json -> {run_dir / 'summary.json'}")
    rep.save(run_dir / "report.txt")
    return 0


# ── sub-command: draft ───────────────────────────────────────────────────────

DRAFT_INSTRUCTIONS = """\
You are proposing a CANDIDATE revision of a production options-flow analysis prompt.
The revision will be SCORED against the shipped prompt by a pre-registered harness;
it is never applied automatically and it is never a ship.

You are given three things:
  1. PROMPT-ROBUSTNESS FINDINGS — empirical findings about where the SHIPPED prompt's
     own prose predicts a worse outcome. These are what the revision must answer.
  2. The current framework file (config/prompts/analysis-framework.md).
  3. The current method file (config/prompts/analysis-methods/claude.md).

Write a MINIMAL, TARGETED revision that answers the findings and changes nothing else.

HARD RULES — a revision that breaks one of these is unscoreable:
  - Do NOT change the output JSON contract (keys: regime, signals, themes, plays,
    invalidation) or any emitted field name.
  - Per-play `regime` and `signal` are TICKER-SPECIFIC and must never fall back to the
    market read.
  - Do NOT change the structure universe, the deployment ladder, sizing, or exits.
  - Do NOT introduce bear_call_spread; it is vetoed at intake.
  - Keep each file's overall structure. Edits should be surgical and reviewable.

Return EXACTLY the three blocks below and nothing else — no preamble, no commentary
outside the blocks.

<<<FILE: analysis-framework.md>>>
(the COMPLETE revised framework file)
<<<END>>>
<<<FILE: claude.md>>>
(the COMPLETE revised method file)
<<<END>>>
<<<FILE: CANDIDATE.md>>>
(markdown: what changed, why, and which finding each edit answers)
<<<END>>>
"""

_BLOCK_RE = re.compile(r"<<<FILE:\s*(?P<name>[^>]+?)\s*>>>\n(?P<body>.*?)\n?<<<END>>>",
                       re.DOTALL)


def claude_text(prompt: str, model: str, timeout: int = 1800) -> str:
    """One headless `claude -p` call, returning the final message text.

    Mirrors `analysis_pipeline.core._invoke_claude`'s invocation and result
    parsing (the CLI may emit a single object or an event array).
    """
    proc = subprocess.run(
        ["claude", "-p", "--output-format", "json", "--model", model],
        input=prompt, capture_output=True, text=True, cwd=str(ROOT),
        timeout=timeout, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {(proc.stderr or '')[:500]}")
    parsed = json.loads(proc.stdout)
    if isinstance(parsed, list):
        results = [e for e in parsed if isinstance(e, dict) and e.get("type") == "result"]
        wrapper = results[-1] if results else {}
    else:
        wrapper = parsed
    if wrapper.get("is_error"):
        raise RuntimeError(f"claude reported error: {wrapper.get('result')}")
    return wrapper.get("result", "")


def cmd_draft(args) -> int:
    """A RECORD, never an application. Nothing here writes config/prompts/."""
    rep = Report()
    out = Path(args.out).resolve()
    findings_path = Path(args.findings)
    if not findings_path.exists():
        raise Refusal(EXIT_MISSING_INPUT, f"findings file not found: {findings_path}")
    if _inside(out, ROOT / "config"):
        raise Refusal(EXIT_ISOLATION,
                      f"--out {out} is inside config/. `draft` writes a CANDIDATE "
                      f"directory; the shipped prompt is changed by an operator, never by "
                      f"this harness.")
    out.mkdir(parents=True, exist_ok=True)

    findings = findings_path.read_text(encoding="utf-8")
    prompt = "\n\n".join([
        DRAFT_INSTRUCTIONS,
        "=== PROMPT-ROBUSTNESS FINDINGS ===",
        findings,
        "=== CURRENT config/prompts/analysis-framework.md ===",
        PROD_FRAMEWORK.read_text(encoding="utf-8"),
        "=== CURRENT config/prompts/analysis-methods/claude.md ===",
        PROD_METHOD.read_text(encoding="utf-8"),
    ])

    rep.hdr("DRAFT — a model-written candidate. NOTHING IS APPLIED.")
    rep(f"  findings   {findings_path}  ({len(findings.splitlines())} lines)")
    rep(f"  model      {args.model}")
    rep(f"  out        {out}")
    rep(f"  PROD sha   framework {short_sha(PROD_FRAMEWORK)}  method {short_sha(PROD_METHOD)}")
    (out / "draft-prompt.md").write_text(prompt, encoding="utf-8")

    text = claude_text(prompt, args.model)
    (out / "draft-response.txt").write_text(text, encoding="utf-8")

    blocks = {m.group("name").strip(): m.group("body") for m in _BLOCK_RE.finditer(text)}
    if "CANDIDATE.md" not in blocks or not blocks["CANDIDATE.md"].strip():
        raise Refusal(
            EXIT_MISSING_INPUT,
            "the model returned no CANDIDATE.md block. `run` refuses a candidate "
            "directory without one (the change and its rationale are part of the record), "
            f"so this draft is not scoreable. Raw response: {out / 'draft-response.txt'}")

    written = []
    for name, prod_path in (("analysis-framework.md", PROD_FRAMEWORK),
                            ("claude.md", PROD_METHOD)):
        body = blocks.get(name)
        if body is None or not body.strip():
            body = prod_path.read_text(encoding="utf-8")
            rep(f"  NOTE: no {name} block returned — the PROD file is copied unchanged.")
        else:
            written.append(name)
        (out / name).write_text(body if body.endswith("\n") else body + "\n",
                                encoding="utf-8")
    (out / "CANDIDATE.md").write_text(blocks["CANDIDATE.md"].strip() + "\n", encoding="utf-8")

    # The diff is computed LOCALLY from the returned files rather than trusted
    # from the model: a model-written diff can be malformed or describe an edit
    # it did not make, and this one is guaranteed to describe the files that
    # would actually be scored.
    chunks = []
    for name, prod_path in (("analysis-framework.md", PROD_FRAMEWORK),
                            ("claude.md", PROD_METHOD)):
        chunks.extend(difflib.unified_diff(
            prod_path.read_text(encoding="utf-8").splitlines(keepends=True),
            (out / name).read_text(encoding="utf-8").splitlines(keepends=True),
            fromfile=f"prod/{name}", tofile=f"cand/{name}"))
    (out / "draft.diff").write_text("".join(chunks), encoding="utf-8")

    rep.sub("WRITTEN")
    for f in ("analysis-framework.md", "claude.md", "CANDIDATE.md", "draft.diff"):
        rep(f"  {out / f}")
    rep(f"  files the model actually rewrote: {', '.join(written) or 'none'}")
    rep("")
    rep("  THE DIFF IS A RECORD, NEVER AN APPLICATION. Nothing applies it. To score it,")
    rep("  the operator reviews it and COMMITS this directory as a candidate — which is")
    rep("  what makes it an arm. A draft that is never committed is never scored, and")
    rep("  that is the intended default.")
    rep("  The diff inherits every bias of the text_features list that seeded it.")
    rep.save(out / "report.txt")
    return 0


# ── CLI ──────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="prompt_eval", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("dates", help="select a date set BY THE REGISTERED RULE")
    p.add_argument("--rule", choices=("backfill", "variance"), required=True)
    p.add_argument("--n", type=int, required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--as-of", default=None, help="maturity reference date (default: today)")
    p.add_argument("--exclude", default=None,
                   help="date file to exclude (backfill defaults to the variance set)")
    p.set_defaults(func=cmd_dates)

    p = sub.add_parser("variance", help="PROD x N repeats -> the noise floor")
    p.add_argument("--dates", required=True)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--model", default=None)
    p.add_argument("--force", action="store_true",
                   help="redo dates already present and discard an existing arm book")
    p.set_defaults(func=cmd_variance)

    p = sub.add_parser("run", help="PROD vs CANDIDATE on a date set")
    p.add_argument("--candidate", required=True)
    p.add_argument("--dates", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--model", default=None)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--variance-json", default=None,
                   help="the variance.json holding the floor (default: found beside the run)")
    p.add_argument("--date-set", default="BACKFILL", choices=("BACKFILL", "LIVE", "OTHER"))
    p.add_argument("--skip-citations", action="store_true",
                   help="do not re-fetch analysis inputs; criterion 4 reads NOT EVALUABLE")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("accumulate", help="one new LIVE date for the CANDIDATE arm")
    p.add_argument("--candidate", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--run-dir", required=True)
    p.add_argument("--model", default=None)
    p.add_argument("--variance-json", default=None)
    p.add_argument("--skip-citations", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_accumulate)

    p = sub.add_parser("draft", help="ask a headless model for a candidate; applies NOTHING")
    p.add_argument("--findings", required=True,
                   help="the PROMPT-ROBUSTNESS FINDINGS block from text_features")
    p.add_argument("--out", required=True,
                   help=f"candidate directory to write (conventionally "
                        f"{DRAFT_ROOT.relative_to(ROOT)}/<stamp>/); the registration's "
                        f"bare <stamp>.diff became this directory — see its dated wording "
                        f"correction")
    p.add_argument("--model", default=DRAFT_MODEL)
    p.set_defaults(func=cmd_draft)
    return ap


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # `run.py` forwards the caller's extra args verbatim, INCLUDING the `--`
    # separator (argparse's parse_known_args leaves it in the unknown list).
    # Every other study takes flags, where a leading `--` is harmless; this one
    # takes a sub-command positional, which argparse would then read as the
    # sub-command name itself. Strip the sentinel here rather than asking the
    # operator to remember a different invocation for this one study.
    while argv and argv[0] == "--":
        argv.pop(0)
    try:
        # Startup isolation check, before anything is parsed or spawned.
        forbid_tab(argv)
        args = build_parser().parse_args(argv)
        return args.func(args)
    except Refusal as exc:
        print(f"\nREFUSED — {exc.message}")
        return exc.code


if __name__ == "__main__":
    sys.exit(main())
