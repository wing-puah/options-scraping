"""SPY/^VIX daily closes — the table behind the mechanical-regime exit override.

This is a PRODUCTION input, not a study artifact: `lib/mech_regime.py` labels
every date from it, `config/backtest.yml` §`simulation.regime_exit` keys the
BEAR_HE trailing stop off those labels, and `mech_cell` on the analysis row is
what the operator reads at deploy time (config/deployment-rules.md §"Exit
management").

It lived in `backtests/mech_regime/fetch_spy_vix.py`, which is untracked
(`.gitignore`: `backtests/*`) — so neither the table nor its fetcher existed
anywhere but one laptop. Moved here so CI can run it and Drive can hold it.

Two directions, deliberately separate:

    fetch_mech_regime.py              # yfinance → local CSV → Drive  (CI)
    fetch_mech_regime.py --download   # Drive → local CSV            (laptop)

Nothing downloads implicitly. `lib/mech_regime.py` stays pure and offline (it is
called per-row inside the backtest), so refreshing is an explicit step — see the
`mech-regime` Makefile target, which `make backtest` and `make analyze` depend
on.

Unadjusted closes (auto_adjust=False) for both tickers, matching the convention
the addendum-4 study was derived under. SPY dividends slightly distort the
50-SMA; that distortion is part of the frozen spec and must not be "fixed" here.
"""
import argparse
import logging
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv

from lib.drive_client import get_drive_client
from lib.logger import setup_logging

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

log = logging.getLogger("fetch_mech_regime")

# Local path read by lib/mech_regime.py (via config/backtest.yml and
# scripts/analysis_pipeline/config.MECH_REGIME_CSV). Untracked by design — the
# copy of record is the Drive one.
LOCAL_PATH = ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv"

# Single file at the Drive ROOT, not under a {YYYY-MM-DD}/ folder: this is one
# continuous series that gets replaced wholesale, not a per-date snapshot.
DRIVE_NAME = "spy-vix-daily.csv"

# Frozen start — 2023-06-01 gives the 50-SMA lookback its runway before the
# first date any analysis covers. Changing it re-labels history.
START = "2023-06-01"


def download() -> int:
    """Drive → local. Returns 0 on success, non-zero if the file isn't there."""
    client = get_drive_client()
    file_id = client.file_exists(DRIVE_NAME, client.root)
    if not file_id:
        log.error("'%s' not in Drive root — run this script without --download "
                  "(or let the Compile Flow workflow do it)", DRIVE_NAME)
        return 1
    content = client.download(file_id, DRIVE_NAME)
    LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_PATH.write_text(content, encoding="utf-8")
    last = content.strip().splitlines()[-1].split(",")[0] if content.strip() else "?"
    log.info("Downloaded %s → %s (%d bytes, through %s)",
             DRIVE_NAME, LOCAL_PATH, len(content), last)
    return 0


def fetch(start: str, end: str, upload: bool) -> int:
    """yfinance → local CSV, then optionally → Drive."""
    try:
        import pandas as pd
        import yfinance as yf
    except ImportError as e:
        log.error("missing dependency: %s", e)
        return 1

    # yfinance's `end` is exclusive for daily bars.
    end_padded = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        spy = yf.download("SPY", start=start, end=end_padded,
                          auto_adjust=False, progress=False)
        vix = yf.download("^VIX", start=start, end=end_padded,
                          auto_adjust=False, progress=False)
    except Exception as e:
        log.error("yfinance download failed: %s", e)
        return 1

    # Never write a partial table — a short series silently re-labels every date
    # whose 50-SMA window it truncates.
    if spy is None or spy.empty:
        log.error("SPY download returned empty data")
        return 1
    if vix is None or vix.empty:
        log.error("^VIX download returned empty data")
        return 1

    def close_col(df):
        # Newer yfinance nests single-ticker frames under a MultiIndex.
        return df["Close"].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df["Close"]

    spy_close, vix_close = close_col(spy), close_col(vix)
    out = pd.DataFrame({
        "date": pd.to_datetime(spy_close.index).strftime("%Y-%m-%d"),
        "spy_close": spy_close.values,
    }).merge(
        pd.DataFrame({
            "date": pd.to_datetime(vix_close.index).strftime("%Y-%m-%d"),
            "vix_close": vix_close.values,
        }),
        on="date", how="outer",
    ).sort_values("date").reset_index(drop=True)

    LOCAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(LOCAL_PATH, index=False)
    log.info("Saved %d rows to %s (%s .. %s); SPY NaNs=%d VIX NaNs=%d",
             len(out), LOCAL_PATH, out["date"].min(), out["date"].max(),
             out["spy_close"].isna().sum(), out["vix_close"].isna().sum())

    if upload:
        client = get_drive_client()
        client.upload(LOCAL_PATH, DRIVE_NAME, client.root)
        log.info("Uploaded %s to Drive root", DRIVE_NAME)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--download", action="store_true",
                    help="pull the table from Drive instead of fetching it")
    ap.add_argument("--no-upload", action="store_true",
                    help="fetch to local only, skip the Drive upload")
    ap.add_argument("--start", default=START)
    ap.add_argument("--end", default=None, help="default: today")
    args = ap.parse_args()

    setup_logging()
    if args.download:
        return download()
    return fetch(args.start, args.end or date.today().isoformat(),
                 upload=not args.no_upload)


if __name__ == "__main__":
    sys.exit(main())
