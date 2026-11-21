"""
Fetcher for the call legs `mechanical_baseline`'s rule trades need.

WHY THIS EXISTS
---------------
`mechanical_baseline` (research/pre-registrations/f1_selection/benchmark/
mechanical_baseline.md, accepted by the operator 2026-10-26) buys one SPY
ATM / +5% call vertical every week at the monthly expiry nearest 65 DTE. The
option cache holds most of those strikes already. A trade whose nearest
listable strike is neither cached nor proven unlisted is AWAITING FETCH, and
while any PRIMARY trade awaits, the study prints NOT BUILT — AWAITING SCRAPE.
This collector fetches them.

TARGETS (`mechanical_baseline.plan`, IMPORTED)
----------------------------------------------
The strikes an awaiting trade names: `mechanical_benchmark.select_m1`'s
nearest-first walk, read on the signal date. A fetch can expose a nearer strike
or prove one unlisted, so the study and this collector alternate until nothing
awaits. Every run recomputes the targets from the cache as it stands, so the
loop is resumable.

  --scope primary  (default) the primary cell, SPY weekly 65, windows A and B
  --scope all      every parameter cell (SPY, QQQ, IWM; weekly, daily,
                   dip-weekly; 65 and 45 DTE), both windows

HOW IT FETCHES
--------------
Through `scripts.backtest.shared.history.fetch_option_histories`, the same loop
the backtest uses (the `fetch_mechanical_legs.py` pattern): one Barchart
session, the `HISTORY_START_DATE` floor, the atomic cache write, the
evidence-gated skip-list and the network-outage abort (exit 6). A 404 is
recorded as unlisted there, which lets the study's walk step past a strike that
is not listed.

ONE WRITER. Two writers into the option cache is how duplicates were made
before. A real fetch REFUSES (exit 3) while another cache writer runs: a
backtest/proxy, the journal, or any other `fetch_*_legs.py` collector,
`mechanical_benchmark`'s ARM U loop included. The check reads one `ps` table and counts only
a Python interpreter running a writer script or module, so this process, its
ancestors (shell, `caffeinate`, `rtk`) and any command that merely names the
script as text are never counted.
`--dry-run` writes nothing and is not refused.

`--dry-run` is offline: it reads the cache index and the skip-list from disk
and prints the count. Nothing below the dry-run return touches the network.

Needs BARCHART_EMAIL/BARCHART_PASSWORD for a real fetch. Research tier, run by
hand. Run `python3 scripts/backup_research_caches.py push` after it.

Usage:
  python3 scripts/collector/study_legs/f1_selection/fetch_mechanical_baseline_legs.py --dry-run
  python3 scripts/collector/study_legs/f1_selection/fetch_mechanical_baseline_legs.py --limit 50
  python3 scripts/collector/study_legs/f1_selection/fetch_mechanical_baseline_legs.py --scope all --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import re
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[4]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from lib.logger import setup_logging  # noqa: E402
from scripts.backtest_study.f1_selection.benchmark import mechanical_baseline as MBL  # noqa: E402
from scripts.collector.study_legs.f1_selection.fetch_mechanical_legs import (  # noqa: E402
    BACKUP_REMINDER, to_contracts,
)

log = logging.getLogger("fetch_mechanical_baseline_legs")

SCOPES = ("primary", "all")
EXIT_OTHER_WRITER = 3
#: Cache writers this collector must not run beside, as regexes on the writer's
#: TARGET: the `-m` module, or the script path a Python interpreter runs.
WRITER_PATTERNS = (r"^scripts\.backtest(\.proxy)?$",
                   r"^scripts\.journal(\.|$)",
                   r"fetch_[a-z_]*legs\.py$")
_PYTHON = re.compile(r"^[Pp]ython(\d+(\.\d+)*)?$")


def process_table(run=subprocess.run) -> list[tuple[str, str, str]]:
    """`[(pid, ppid, command)]` for every process, from one `ps` call."""
    res = run(["ps", "-axo", "pid=,ppid=,command="], capture_output=True, text=True)
    rows = []
    for line in (res.stdout or "").splitlines():
        parts = line.split(None, 2)
        if len(parts) == 3:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def ancestry(pid: int | None = None, table=None, run=subprocess.run) -> set[str]:
    """This process and every parent: a wrapper (`caffeinate`, a shell, `rtk`,
    `make`) carries this script's name on its command line and is not another
    writer."""
    rows = process_table(run) if table is None else table
    parent = {p: pp for p, pp, _ in rows}
    out, cur = set(), str(pid if pid is not None else os.getpid())
    while cur and cur not in out and cur != "0":
        out.add(cur)
        cur = parent.get(cur, "")
    return out


def writer_target(command: str) -> str | None:
    """What a Python interpreter command line runs: the `-m` module or the script
    path. None when the command is not a Python interpreter, so a shell `-c`
    string, `tail`, `grep` or an editor that merely names a script never counts."""
    try:
        argv = shlex.split(command)
    except ValueError:
        argv = command.split()
    if not argv or not _PYTHON.match(os.path.basename(argv[0])):
        return None
    args = argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-m":
            return args[i + 1] if i + 1 < len(args) else None
        if a == "-c":
            return None
        if a in ("-W", "-X"):
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        return a
    return None


def other_writers(patterns=WRITER_PATTERNS, own: set[str] | None = None,
                  run=subprocess.run, table=None) -> list[tuple[str, str]]:
    """`[(pid, pattern)]` of running Python processes that write the option
    cache. This process, its ancestors and the scan's own children are excluded."""
    rows = process_table(run) if table is None else table
    own = ancestry(table=rows) if own is None else own
    found = []
    for pid, ppid, cmd in rows:
        if pid in own or ppid == str(os.getpid()):
            continue
        target = writer_target(cmd)
        if target is None:
            continue
        for pat in patterns:
            if re.search(pat, target):
                found.append((pid, pat))
                break
    return found


async def fetch(targets: list[dict], headless: bool, timeout_ms: int) -> int:
    from scripts.backtest.shared.history import fetch_option_histories
    contracts = to_contracts(targets)
    series, _details = await fetch_option_histories(
        contracts, headless, timeout_ms, retry_unlisted=True)
    return sum(1 for c in contracts if series.get(c["key"]))


def main(argv=None) -> int:
    setup_logging()
    log.setLevel(logging.INFO)
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the contract count; no network, no write.")
    ap.add_argument("--list", action="store_true",
                    help="With --dry-run, also print every contract.")
    ap.add_argument("--scope", default="primary", choices=SCOPES,
                    help="primary (default): SPY weekly 65; all: every parameter cell.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Fetch at most N contracts this run (resumable).")
    ap.add_argument("--no-headless", action="store_true", help="Visible browser.")
    ap.add_argument("--timeout-ms", type=int, default=15000)
    args = ap.parse_args(argv)

    if not args.dry_run:
        busy = other_writers()
        if busy:
            pid, pat = busy[0]
            print(f"REFUSED: another option-cache writer is running (PID {pid}, "
                  f"matched {pat!r}). One writer at a time.", file=sys.stderr)
            return EXIT_OTHER_WRITER

    from scripts.backtest.shared.history import EXIT_NETWORK_OUTAGE, NetworkOutage

    targets = MBL.plan(args.scope)
    todo = targets if args.limit is None else targets[:args.limit]
    by = Counter(t["category"] for t in targets)
    cats = "  ".join(f"{k}={v}" for k, v in sorted(by.items()))
    print(f"unique uncached call contracts to fetch ({args.scope}): {len(targets)}  {cats}")
    if args.limit is not None:
        print(f"this run fetches at most {args.limit}")
    if args.dry_run:
        if args.list:
            for t in todo:
                print(f"  {t['ticker']:<6} {t['expiration'].isoformat()} "
                      f"{t['strike']:>9.2f}C  {t['category']}")
        print("[dry-run] nothing fetched")
        print(BACKUP_REMINDER)
        return 0
    if not todo:
        print("Nothing to fetch.")
        return 0
    headless = not args.no_headless and os.getenv("SCRAPE_HEADLESS", "true").lower() == "true"
    try:
        got = asyncio.run(fetch(todo, headless, args.timeout_ms))
    except NetworkOutage as e:
        log.error("network outage: %d of %d fetches failed — stopped; what was "
                  "written is kept, re-run when online", e.n_failed, e.n_total)
        print(BACKUP_REMINDER)
        return EXIT_NETWORK_OUTAGE
    print(f"fetched {got} of {len(todo)} requested; "
          f"{len(targets) - len(todo)} left for a later run")
    print(BACKUP_REMINDER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
