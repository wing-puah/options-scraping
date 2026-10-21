"""Daily regime watch: a REPORT on whether a SPY BEAR flip is holding. Not a rule.

Changes no tier, sizing or exit, and nothing in production reads it. It sits
beside the frozen mechanical label (`lib/mech_regime.py`, imported by the script,
never re-implemented here) and asks five questions of the tape.

The thresholds below are EXPLORATORY and UNVALIDATED. They come from a
2026-10-21 exploratory pass on 97 SPY BEAR flips since 1993. A pre-registration
is pending under research/pre-registrations/f1_selection/regime/; until it is
filed and graded, treat every line this prints as a description of the tape,
not as evidence that the checklist predicts anything.

Checklist (1 is persistence, 2-5 are the confirmations):
    1. persistence  consecutive sessions the mech direction has been BEAR (>= 3)
    2. SPY close below its 200-day SMA            (unadjusted Close)
    3. credit weak  HYG/IEF ratio 20-session change < -1%   (Adj Close)
    4. IWM close below its 200-day SMA            (unadjusted Close)
    5. VIX close >= 20

Status:
    CONFIRMED  BEAR streak >= 3 and at least 2 of conditions 2-5 hold
    WATCH      BEAR at any point in the last 5 sessions, or 2+ of 2-5 hold
    CLEAR      otherwise

Pure module: frames and the mech table come in as arguments, no network. A
frame is a DataFrame indexed by date with `Close` and `Adj Close` columns. The
mech table is the list of rows `lib.mech_regime.compute_mech_table` returns.
Every figure for date D uses only data on or before D, so `--as-of` replays are
causal; an in-progress bar for today is dropped before anything is computed.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# Exploratory, unvalidated (see module docstring).
PERSIST_MIN = 3
RECENT_BEAR_WINDOW = 5
LONG_SMA = 200
MID_SMA = 50
CREDIT_WINDOW = 20
CREDIT_FLOOR = -0.01
VIX_LEVEL = 20.0
CONFIRM_MIN = 2

# A US cash session is complete from 16:00 ET; 16:15 leaves room for the print.
# A fixed UTC-5 offset keeps this free of tz data; it errs a bar late in summer
# (21:15 UTC is 17:15 EDT), never early.
_CLOSE_UTC = (21, 15)

HISTORY_COLUMNS = [
    "date", "status", "bear_streak", "bear_recent5",
    "c1_persistence", "c2_spy_below_200", "c3_credit_weak", "c4_iwm_below_200",
    "c5_vix_ge_20", "n_confirm",
    "spy_close", "spy_sma200", "credit_chg20", "iwm_close", "iwm_sma200",
    "vix_close", "vix_vix3m", "spy_vs_sma50", "mech_direction", "mech_vol",
    "mech_asof",
]


def drop_partial(df: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    """Drop bars that are not a finished session: NaN Close, future dates, and
    today's bar until the cash close has printed (like `lib.mech_regime`, which
    refuses to label today off a partial bar)."""
    if df is None or df.empty:
        return df
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    today = now.astimezone(timezone.utc).date()
    done_today = (now.hour, now.minute) >= _CLOSE_UTC
    out = df[df["Close"].notna()]
    idx = pd.to_datetime(out.index).normalize()
    keep = (idx.date < today) if not done_today else (idx.date <= today)
    return out[keep]


def truncate(df: pd.DataFrame, as_of: str) -> pd.DataFrame:
    """Rows dated on or before `as_of` only. The single lookahead guard."""
    idx = pd.to_datetime(df.index).normalize()
    return df[idx <= pd.Timestamp(as_of)]


def bear_streak(table: list[dict], as_of: str) -> tuple[int, bool, dict | None]:
    """(consecutive BEAR sessions ending at the last row <= as_of,
    any BEAR in the last RECENT_BEAR_WINDOW rows, that last row)."""
    rows = [r for r in table if r["date"] <= as_of]
    if not rows:
        return 0, False, None
    streak = 0
    for r in reversed(rows):
        if r["mech_direction"] == "BEAR":
            streak += 1
        else:
            break
    recent = any(r["mech_direction"] == "BEAR" for r in rows[-RECENT_BEAR_WINDOW:])
    return streak, recent, rows[-1]


def classify(streak: int, recent_bear: bool, n_confirm: int) -> str:
    if streak >= PERSIST_MIN and n_confirm >= CONFIRM_MIN:
        return "CONFIRMED"
    if recent_bear or n_confirm >= CONFIRM_MIN:
        return "WATCH"
    return "CLEAR"


def _last(df: pd.DataFrame, col: str = "Close"):
    if df is None or df.empty:
        return None
    v = df[col].iloc[-1]
    return None if v != v else float(v)


def _below_sma(df: pd.DataFrame, window: int):
    """(close, sma, close < sma). None triple when the runway is short."""
    if df is None or len(df) < window:
        return (_last(df), None, None)
    close = float(df["Close"].iloc[-1])
    sma = float(df["Close"].iloc[-window:].mean())
    return close, sma, close < sma


def _credit_change(hyg: pd.DataFrame, ief: pd.DataFrame):
    """20-session change of the HYG/IEF Adj Close ratio on common dates."""
    if hyg is None or ief is None or hyg.empty or ief.empty:
        return None
    ratio = (hyg["Adj Close"] / ief["Adj Close"]).dropna()
    if len(ratio) <= CREDIT_WINDOW:
        return None
    return float(ratio.iloc[-1] / ratio.iloc[-1 - CREDIT_WINDOW] - 1.0)


def evaluate(frames: dict[str, pd.DataFrame], mech_table: list[dict],
             as_of: str | None = None, now: datetime | None = None) -> dict:
    """The whole report for one date. `as_of` None means the latest finished
    SPY session; a given date means the latest SPY session on or before it.
    """
    f = {}
    for k, df in frames.items():
        if df is None:
            continue
        df = drop_partial(df, now)
        if as_of:
            df = truncate(df, as_of)
        f[k] = df
    spy = f.get("SPY")
    if spy is None or spy.empty:
        raise ValueError("no finished SPY session on or before as-of")
    date = pd.Timestamp(spy.index[-1]).strftime("%Y-%m-%d")
    # Every other series is cut to the SPY session so one lagging ticker cannot
    # make a figure come from a different day.
    f = {k: truncate(df, date) for k, df in f.items()}

    streak, recent, mech_row = bear_streak(
        [r for r in mech_table if r["date"] <= date], date)
    spy_close, spy_sma200, c2 = _below_sma(f["SPY"], LONG_SMA)
    iwm_close, iwm_sma200, c4 = _below_sma(f.get("IWM"), LONG_SMA)
    credit = _credit_change(f.get("HYG"), f.get("IEF"))
    c3 = None if credit is None else round(credit, 9) < CREDIT_FLOOR  # round: -1.0% exactly is not weak
    vix = _last(f.get("^VIX"))
    c5 = None if vix is None else vix >= VIX_LEVEL
    conds = {"c2_spy_below_200": c2, "c3_credit_weak": c3,
             "c4_iwm_below_200": c4, "c5_vix_ge_20": c5}
    n_confirm = sum(1 for v in conds.values() if v is True)

    vix3m = _last(f.get("^VIX3M"))
    sma50 = float(f["SPY"]["Close"].iloc[-MID_SMA:].mean()) if len(f["SPY"]) >= MID_SMA else None
    last10 = [{"date": r["date"], "direction": r["mech_direction"], "vol": r["mech_vol"]}
              for r in [r for r in mech_table if r["date"] <= date][-10:]]
    return {
        "date": date,
        "status": classify(streak, recent, n_confirm),
        "bear_streak": streak,
        "bear_recent5": recent,
        "c1_persistence": streak >= PERSIST_MIN,
        **conds,
        "n_confirm": n_confirm,
        "spy_close": spy_close, "spy_sma200": spy_sma200,
        "credit_chg20": credit,
        "iwm_close": iwm_close, "iwm_sma200": iwm_sma200,
        "vix_close": vix,
        "vix_vix3m": (vix / vix3m) if (vix is not None and vix3m) else None,
        "spy_vs_sma50": (spy_close / sma50 - 1.0) if sma50 else None,
        "mech_direction": mech_row["mech_direction"] if mech_row else None,
        "mech_vol": mech_row["mech_vol"] if mech_row else None,
        "mech_asof": mech_row["date"] if mech_row else None,
        "last10": last10,
    }


def upsert_history(path: str | Path, row: dict) -> int:
    """Write `row` into the history CSV, replacing any row with the same date.
    Returns the row count. Rows stay sorted by date."""
    p = Path(path)
    rows: list[dict] = []
    if p.exists():
        with open(p, newline="") as fh:
            rows = list(csv.DictReader(fh))
    flat = {c: ("" if row.get(c) is None else row.get(c)) for c in HISTORY_COLUMNS}
    rows = [r for r in rows if r.get("date") != flat["date"]]
    rows.append({k: str(v) for k, v in flat.items()})
    rows.sort(key=lambda r: r["date"])
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=HISTORY_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in HISTORY_COLUMNS})
    return len(rows)
