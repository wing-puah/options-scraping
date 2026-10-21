"""Daily regime watch: a REPORT, not a rule. Nothing in production reads it.

    python3 scripts/regime_watch.py                    # latest finished session
    python3 scripts/regime_watch.py --as-of 2025-04-08 # causal replay
    python3 scripts/regime_watch.py --json             # same content as JSON
    python3 scripts/regime_watch.py --backfill 250     # replay the last 250 sessions into history
    make regime-watch ARGS="--as-of 2025-04-08"

Fetches ~300 sessions of SPY, IWM, HYG, IEF, ^VIX, ^VIX3M from yfinance, takes
the direction/vol label from the frozen mech table (`lib/mech_regime.py`, refreshed
by fetch_mech_regime.py), and prints the five-line checklist in `lib/regime_watch.py`.
The thresholds there are UNVALIDATED (exploratory pass 2026-10-21; a
pre-registration is pending under research/pre-registrations/f1_selection/regime/).

SPY/IWM moving averages use unadjusted Close; the HYG/IEF ratio uses Adj Close.
Appends one row per run to backtests/regime_watch/history.csv (deduped on date).
Exit 1 if the data cannot be fetched.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib import mech_regime, regime_watch  # noqa: E402

MECH_CSV = ROOT / "backtests" / "mech_regime" / "spy_vix_daily_full.csv"
HISTORY = ROOT / "backtests" / "regime_watch" / "history.csv"
REQUIRED = ("SPY", "IWM", "HYG", "IEF", "^VIX")
OPTIONAL = ("^VIX3M",)
LOOKBACK_DAYS = 480  # ~330 sessions: 200-SMA plus runway


def fetch(as_of: str | None, extra_days: int = 0) -> dict:
    import pandas as pd
    import yfinance as yf

    end = pd.Timestamp(as_of) if as_of else pd.Timestamp(date.today())
    start = (end - pd.Timedelta(days=LOOKBACK_DAYS + extra_days)).strftime("%Y-%m-%d")
    end_pad = (end + pd.Timedelta(days=1)).strftime("%Y-%m-%d")  # end is exclusive
    frames = {}
    for t in REQUIRED + OPTIONAL:
        try:
            df = yf.download(t, start=start, end=end_pad, auto_adjust=False,
                             progress=False)
        except Exception:
            df = None
        if df is None or df.empty:
            if t in REQUIRED:
                raise RuntimeError(f"{t} download returned no data")
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        frames[t] = df[["Close", "Adj Close"]].copy()
    return frames


def _f(v, fmt):
    return "n/a" if v is None else format(v, fmt)


def _mark(v):
    return "n/a" if v is None else ("YES" if v else "no")


def render(r: dict) -> str:
    lines = [f"Regime watch {r['date']}  (mech {r['mech_direction']}/{r['mech_vol']} as of {r['mech_asof']})",
             "-" * 64,
             f"1 BEAR streak >= 3      {_mark(r['c1_persistence']):>4}   streak {r['bear_streak']}",
             f"2 SPY < 200d SMA        {_mark(r['c2_spy_below_200']):>4}   {_f(r['spy_close'], '.2f')} vs {_f(r['spy_sma200'], '.2f')}",
             f"3 credit weak           {_mark(r['c3_credit_weak']):>4}   HYG/IEF 20d {_f(None if r['credit_chg20'] is None else r['credit_chg20'] * 100, '+.2f')}%",
             f"4 IWM < 200d SMA        {_mark(r['c4_iwm_below_200']):>4}   {_f(r['iwm_close'], '.2f')} vs {_f(r['iwm_sma200'], '.2f')}",
             f"5 VIX >= 20             {_mark(r['c5_vix_ge_20']):>4}   {_f(r['vix_close'], '.2f')}",
             "-" * 64,
             f"info: VIX/VIX3M {_f(r['vix_vix3m'], '.3f')} | SPY vs 50d SMA "
             f"{_f(None if r['spy_vs_sma50'] is None else r['spy_vs_sma50'] * 100, '+.2f')}%",
             "last 10: " + " ".join(f"{x['date'][5:]}:{x['direction'] or '-'}/{x['vol'] or '-'}" for x in r["last10"]),
             f"STATUS: {r['status']}  (BEAR streak {r['bear_streak']}, "
             f"{r['n_confirm']}/4 confirmations, BEAR in last 5: {'yes' if r['bear_recent5'] else 'no'})"
             "  [UNVALIDATED thresholds; report only]"]
    return "\n".join(lines)


def backfill(frames: dict, table: list[dict], sessions: int, history: str) -> int:
    """Replay the last `sessions` SPY sessions one as-of at a time into history.

    evaluate() cuts every series to the as-of date, so each row is what a run on
    that day would have printed (the mech table is causal the same way)."""
    spy = regime_watch.drop_partial(frames["SPY"])
    days = [d.strftime("%Y-%m-%d") for d in spy.index[-sessions:]]
    for d in days:
        regime_watch.upsert_history(history, regime_watch.evaluate(frames, table, as_of=d))
    return len(days)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as-of", help="YYYY-MM-DD; use only data on or before it")
    ap.add_argument("--json", action="store_true", help="print JSON instead of the table")
    ap.add_argument("--no-history", action="store_true", help="do not append to the history CSV")
    ap.add_argument("--history", default=str(HISTORY))
    ap.add_argument("--backfill", type=int, metavar="N",
                    help="replay the last N sessions into the history CSV, then exit")
    ap.add_argument("--mech-csv", default=str(MECH_CSV))
    args = ap.parse_args()

    if not Path(args.mech_csv).exists():
        print(f"regime_watch: mech table missing at {args.mech_csv}; run `make mech-regime`",
              file=sys.stderr)
        return 1
    try:
        frames = fetch(args.as_of, extra_days=int((args.backfill or 0) * 1.5))
        table = mech_regime.compute_mech_table(args.mech_csv)
        if args.backfill:
            n = backfill(frames, table, args.backfill, args.history)
            print(f"regime_watch: {n} sessions replayed into {args.history}")
            return 0
        r = regime_watch.evaluate(frames, table, as_of=args.as_of)
    except Exception as e:
        print(f"regime_watch: {e}", file=sys.stderr)
        return 1

    if r["mech_asof"] != r["date"]:
        print(f"WARNING: mech table ends {r['mech_asof']}, before {r['date']}; "
              f"streak/direction are stale (make mech-regime)", file=sys.stderr)
    if not args.no_history:
        regime_watch.upsert_history(args.history, r)
    print(json.dumps(r, indent=2) if args.json else render(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
