"""
Barchart options scraper — live and historical.

Live mode (default): scrapes today's data for the selected type.
Historical mode (--date / --start + --end): scrapes all four data types for past dates.

Usage:
  # Live — run during/after market hours
  python3 scripts/collector/scrape_flow.py --mode flow
  python3 scripts/collector/scrape_flow.py --mode unusual

  # Historical — backfill a date or date range
  python3 scripts/collector/scrape_flow.py --date 2026-04-21
  python3 scripts/collector/scrape_flow.py --start 2026-01-02 --end 2026-05-30 --skip-existing
"""
import argparse
import asyncio
import csv
import logging
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")

_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(_ROOT))

from lib.logger import setup_logging
from lib.barchart import BarchartSession
from lib.csv_utils import flow_staleness_report, parse_csv
from lib.drive_client import StorageClient, file_name, get_drive_client, trading_day

log = logging.getLogger("scrape_flow")

# Staleness-guard bookkeeping. Barchart serves a schema-correct FALLBACK payload
# for dates past the options-flow retention window, so every download is checked
# against the date it was requested for before it is allowed into Drive.
MANIFEST_PATH = _ROOT / "backtests" / "flow_scrape_manifest.csv"
MANIFEST_COLUMNS = [
    "requested_date", "prefix", "verdict", "reasons", "flags",
    "rows", "sha256", "median_dte", "max_dte", "spy_drift",
]
SPY_VIX_CSV = _ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv"

_REJECTED = -2   # distinct from -1 (download failure) so the two are counted apart

ET = ZoneInfo("America/New_York")

BARCHART_EMAIL    = os.getenv("BARCHART_EMAIL", "")
BARCHART_PASSWORD = os.getenv("BARCHART_PASSWORD", "")
COOKIES_PATH = Path(
    os.getenv("COOKIES_PATH", str(_ROOT / "cookies" / "barchart_session.json"))
)
HEADLESS = os.getenv("SCRAPE_HEADLESS", "false").lower() == "true"

# Live URLs — current day's data, split by --mode
_LIVE_PAGES = {
    "flow": [
        ("https://www.barchart.com/options/options-flow/stocks", "stocks-flow"),
        ("https://www.barchart.com/options/options-flow/etfs",   "etfs-flow"),
    ],
    "unusual": [
        ("https://www.barchart.com/options/unusual-activity/stocks", "unusual-stocks"),
        ("https://www.barchart.com/options/unusual-activity/etfs",   "unusual-etfs"),
    ],
}

# Historical base URLs — &historicalDate=YYYY-MM-DD appended at runtime; always all four
_HIST_BASE_PAGES = [
    ("https://www.barchart.com/options/unusual-activity/stocks?type=historical", "unusual-stocks"),
    ("https://www.barchart.com/options/unusual-activity/etfs?type=historical",   "unusual-etfs"),
    ("https://www.barchart.com/options/options-flow/stocks?type=historical",     "stocks-flow"),
    ("https://www.barchart.com/options/options-flow/etfs?type=historical",       "etfs-flow"),
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def trading_days(start: date, end: date) -> list[date]:
    """Return all weekdays (Mon–Fri) between start and end, inclusive."""
    days, current = [], start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def is_market_hours(now: datetime | None = None) -> bool:
    """Return True if now falls within Mon-Fri 09:30-16:00 ET."""
    now = now or datetime.now(ET)
    if now.weekday() >= 5:
        return False
    open_t  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0,  second=0, microsecond=0)
    return open_t <= now <= close_t


# ── Staleness guard helpers ───────────────────────────────────────────────────

def _load_spy_closes() -> dict[str, float]:
    """{ISO date: SPY close} for the ETF-feed price anchor.

    Read directly rather than through lib.mech_regime.MechLabeler: that exposes
    regime labels, not raw closes, and computing the whole mech table here would
    be wasted work. Missing file is soft — the anchor check simply won't run.
    """
    closes: dict[str, float] = {}
    if not SPY_VIX_CSV.exists():
        log.warning("staleness guard: %s missing — SPY anchor check disabled", SPY_VIX_CSV)
        return closes
    with SPY_VIX_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                closes[(row.get("date") or "")[:10]] = float(row["spy_close"])
            except (TypeError, ValueError, KeyError):
                continue
    return closes


def _manifest_hashes() -> dict[str, str]:
    """{sha256: requested_date} for payloads already accepted.

    A digest reappearing under a DIFFERENT date is the byte-identical-payload
    signature of the fallback feed.
    """
    seen: dict[str, str] = {}
    if not MANIFEST_PATH.exists():
        return seen
    with MANIFEST_PATH.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("verdict") == "ok" and row.get("sha256"):
                seen.setdefault(row["sha256"], row.get("requested_date", ""))
    return seen


def _manifest_append(report: dict, requested_date: str, prefix: str) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_new = not MANIFEST_PATH.exists()
    with MANIFEST_PATH.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "requested_date": requested_date,
            "prefix": prefix,
            "verdict": report["verdict"],
            "reasons": "; ".join(report["reasons"]),
            "flags": "; ".join(report["flags"]),
            "rows": report["rows"],
            "sha256": report["sha256"],
            "median_dte": report.get("median_dte"),
            "max_dte": report.get("max_dte"),
            "spy_drift": report.get("spy_drift"),
        })


# ── Core download + upload (shared by both modes) ─────────────────────────────

async def _download_and_upload(
    session: BarchartSession,
    client: StorageClient,
    url: str,
    prefix: str,
    run_dt: datetime,
    folder_id: str,
    target_date: date,
    spy_close: float | None = None,
    seen_hashes: dict[str, str] | None = None,
    allow_stale: bool = False,
) -> int:
    """Download one Barchart page and upload to Drive.

    Returns the row count, -1 on download failure, or _REJECTED when the payload
    failed the staleness guard (in which case nothing is uploaded).
    """
    name = file_name(prefix, run_dt)
    if client.file_exists(name, folder_id):
        log.info("%s: '%s' already in Drive — skipping", prefix, name)
        return 0

    log.info("%s: downloading from '%s'", prefix, url)
    try:
        raw = await session.download_csv(url)
    except Exception:
        log.exception("%s: download failed", prefix)
        return -1

    if raw is None:
        log.warning("%s: download returned no data", prefix)
        return -1

    rows = parse_csv(raw)
    if not rows:
        log.warning("%s: CSV parsed 0 rows", prefix)
        return 0

    # Staleness guard — establish that this payload really is target_date's tape
    # before it is allowed to become part of the corpus.
    report = flow_staleness_report(rows, target_date, spy_close=spy_close)
    prior = (seen_hashes or {}).get(report["sha256"])
    if prior and prior != target_date.isoformat():
        report["reasons"].append(f"duplicate_payload (identical to {prior})")
        report["verdict"] = "reject"
    _manifest_append(report, target_date.isoformat(), prefix)

    if report["verdict"] == "reject":
        # A rejected payload is NEVER uploaded, flag or not. --allow-stale only
        # says "this run expects rejections" (the retention probe), so they are
        # recorded at info level instead of being shouted about as failures.
        detail = "; ".join(report["reasons"])
        if allow_stale:
            log.info("%s: stale payload for %s (expected) — %s", prefix, target_date, detail)
        else:
            log.error("%s: STALE payload for %s — not uploaded — %s",
                      prefix, target_date, detail)
        return _REJECTED
    if report["flags"]:
        log.warning("%s: %s", prefix, "; ".join(report["flags"]))
    if seen_hashes is not None:
        seen_hashes.setdefault(report["sha256"], target_date.isoformat())

    tmp = Path(f"/tmp/{name}")
    tmp.write_text(raw, encoding="utf-8")
    client.upload(tmp, name, folder_id)
    tmp.unlink(missing_ok=True)

    log.info("%s: %d rows → Drive (file='%s')", prefix, len(rows), name)
    return len(rows)


# ── Live mode ──────────────────────────────────────────────────────────────────

async def run_live(session: BarchartSession, client: StorageClient, mode: str) -> None:
    run_dt = datetime.now(ET)
    date_str = trading_day()
    folder_id = client.get_or_create_date_folder(date_str)
    log.info("Live | mode=%s | date=%s", mode, date_str)

    spy_closes = _load_spy_closes()
    seen_hashes = _manifest_hashes()
    target_date = date.fromisoformat(date_str)

    for url, prefix in _LIVE_PAGES[mode]:
        await _download_and_upload(
            session, client, url, prefix, run_dt, folder_id,
            target_date=target_date,
            spy_close=spy_closes.get(date_str),
            seen_hashes=seen_hashes,
        )


# ── Historical mode ────────────────────────────────────────────────────────────

def _already_collected(client: StorageClient, prefix: str, target_date: date) -> bool:
    compact = target_date.strftime("%Y%m%d")
    return any(f["name"].startswith(f"{prefix}-{compact}-") for f in client.list_files(prefix))


async def run_historical(
    session: BarchartSession,
    client: StorageClient,
    dates: list[date],
    skip_existing: bool,
    allow_stale: bool = False,
) -> None:
    total_rows, errors, rejected = 0, 0, 0
    spy_closes = _load_spy_closes()
    seen_hashes = _manifest_hashes()

    for i, target_date in enumerate(dates, 1):
        date_str = target_date.isoformat()
        folder_id = client.get_or_create_date_folder(date_str)
        run_dt = datetime(target_date.year, target_date.month, target_date.day, 16, 0)
        log.info("[%d/%d] Historical | date=%s", i, len(dates), date_str)

        for base_url, prefix in _HIST_BASE_PAGES:
            if skip_existing and _already_collected(client, prefix, target_date):
                log.info("%s: already in Drive for %s — skipping", prefix, date_str)
                continue

            url = f"{base_url}&historicalDate={date_str}"
            count = await _download_and_upload(
                session, client, url, prefix, run_dt, folder_id,
                target_date=target_date,
                spy_close=spy_closes.get(date_str),
                seen_hashes=seen_hashes,
                allow_stale=allow_stale,
            )
            if count > 0:
                total_rows += count
            elif count == _REJECTED:
                rejected += 1
            elif count < 0:
                errors += 1
            await asyncio.sleep(2)

        if i < len(dates):
            await asyncio.sleep(3)

    # `rejected` is reported apart from `errors`: a rejection means Barchart
    # answered but with someone else's data, which is a data-integrity event,
    # not a transport failure.
    log.info("Historical complete — %d total rows, %d errors, %d rejected (stale)",
             total_rows, errors, rejected)


# ── Entry point ────────────────────────────────────────────────────────────────

async def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(
        description="Scrape Barchart options data (live or historical) to Google Drive.",
    )
    parser.add_argument(
        "--mode", choices=["flow", "unusual"], default="flow",
        help="Live mode only: which data type to scrape (default: flow)",
    )
    parser.add_argument("--date",  help="Historical: single date (YYYY-MM-DD)")
    parser.add_argument("--start", help="Historical: start date (YYYY-MM-DD)")
    parser.add_argument("--end",   help="Historical: end date (YYYY-MM-DD), defaults to today")
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="Historical: skip prefix+date combos already present in Drive",
    )
    parser.add_argument(
        "--allow-stale", action="store_true",
        help="Historical: expect staleness rejections (retention probe). Records "
             "each verdict to the manifest at info level; still never uploads.",
    )
    args = parser.parse_args()

    historical = bool(args.date or args.start)

    if not BARCHART_EMAIL or not BARCHART_PASSWORD:
        log.error("BARCHART_EMAIL and BARCHART_PASSWORD must be set")
        sys.exit(1)

    client = get_drive_client()

    if historical:
        if args.date:
            dates = [date.fromisoformat(args.date)]
        else:
            start = date.fromisoformat(args.start)
            end = date.fromisoformat(args.end) if args.end else date.today()
            dates = trading_days(start, end)
        log.info("Mode: historical | %d trading day(s)", len(dates))
    else:
        if not is_market_hours():
            log.info("Outside market hours (Mon-Fri 09:30-16:00 ET) — proceeding anyway")
        log.info("Mode: live | %s", args.mode)

    async with BarchartSession(BARCHART_EMAIL, BARCHART_PASSWORD, COOKIES_PATH, HEADLESS) as session:
        if historical:
            await run_historical(session, client, dates, args.skip_existing,
                                 allow_stale=args.allow_stale)
        else:
            await run_live(session, client, args.mode)

    log.info("Done")


if __name__ == "__main__":
    asyncio.run(main())
