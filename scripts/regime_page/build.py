"""The dashboard's "Regime watch" section: the regime-watch status set against SPY, QQQ and SMH.

Reads local files only: `backtests/regime_watch/history.csv` and the underlying OHLC cache
(through `load_bars`, as the put/call page does). It computes nothing the status itself
does not already say. It lists what each ETF did while the status held, so a reader can see
that CONFIRMED marks a fall already under way. It forecasts nothing.

`gather` returns a plain dict and degrades to {"ok": False, "why": ...}, as the dashboard's
other gatherers do. Percentages are decimal fractions here and are formatted in `render`.
Sessions are counted on the price calendar (every date any of the three ETFs has a close),
never on the history rows, because the history has gaps.
"""
from __future__ import annotations

import csv
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WATCH_CSV = ROOT / "backtests" / "regime_watch" / "history.csv"
ETFS = ("SPY", "QQQ", "SMH")
HORIZONS = (5, 10, 21)
STATUS_CLS = {"CLEAR": "ship", "WATCH": "open", "CONFIRMED": "con"}
DASH = "—"
NOT_YET = "not yet"

e = html.escape


def default_loader(sym: str) -> dict:
    """{date: close} for one ETF, from the repo's existing OHLC loader."""
    from scripts.backtest_study.lib.underlying import load_bars
    return {d.isoformat(): b.c for d, b in load_bars(sym).items()}


def load_history(path: Path = WATCH_CSV) -> list[dict]:
    """History rows, oldest first, one per date. Missing or unreadable file gives []."""
    try:
        with open(path, newline="", encoding="utf-8") as f:
            raw = list(csv.DictReader(f))
    except (OSError, UnicodeDecodeError, csv.Error):
        return []
    by_date = {}
    for r in raw:
        d = (r.get("date") or "").strip()[:10]
        st = (r.get("status") or "").strip().upper()
        if len(d) == 10 and st:
            by_date[d] = {"date": d, "status": st, "n_confirm": (r.get("n_confirm") or "").strip(),
                          "vix_close": (r.get("vix_close") or "").strip(),
                          "mech_direction": (r.get("mech_direction") or "").strip(),
                          "mech_vol": (r.get("mech_vol") or "").strip()}
    return [by_date[d] for d in sorted(by_date)]


def status_runs(rows: list[dict]) -> list[dict]:
    """Consecutive rows with one status form a run, oldest first. A single row is a run of one."""
    runs: list[dict] = []
    for r in rows:
        if runs and runs[-1]["status"] == r["status"]:
            runs[-1]["end"] = r["date"]
            runs[-1]["rows"] += 1
        else:
            runs.append({"status": r["status"], "start": r["date"], "end": r["date"], "rows": 1})
    return runs


def calendar(prices: dict) -> list[str]:
    """Every date any of the ETFs has a close, ascending."""
    return sorted({d for series in prices.values() for d in series})


def sessions_between(cal: list[str], start: str, end: str) -> int:
    return sum(1 for d in cal if start <= d <= end)


def pct_change(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or a <= 0:
        return None
    return b / a - 1.0


def run_prices(prices: dict, run: dict) -> dict:
    """Per ETF: close at the run's start and end and the decimal change. None when a close is missing.

    Only the close on the exact date counts; a neighbouring day is never substituted."""
    out = {}
    for sym in ETFS:
        s = prices.get(sym, {})
        a, b = s.get(run["start"]), s.get(run["end"])
        out[sym] = {"start": a, "end": b, "chg": pct_change(a, b)}
    return out


def build_runs(rows: list[dict], prices: dict) -> list[dict]:
    """Table A rows, newest first."""
    cal = calendar(prices)
    out = []
    for run in reversed(status_runs(rows)):
        n_cal = sessions_between(cal, run["start"], run["end"])
        out.append({**run, "sessions": n_cal or run["rows"], "prices": run_prices(prices, run)})
    return out


def forward_return(prices: dict, cal: list[str], sym: str, signal: str, h: int):
    """The close h sessions after the signal-day close, as a decimal change.

    Returns a float, NOT_YET (the horizon has not elapsed on the price calendar) or None (no price)."""
    if signal not in cal:
        return None
    i = cal.index(signal) + h
    if i >= len(cal):
        return NOT_YET
    s = prices.get(sym, {})
    return pct_change(s.get(signal), s.get(cal[i]))


def onsets(rows: list[dict], prices: dict) -> list[dict]:
    """Table B rows, newest first: the first row of every CONFIRMED run."""
    cal = calendar(prices)
    out = []
    for run in reversed(status_runs(rows)):
        if run["status"] != "CONFIRMED":
            continue
        out.append({"date": run["start"],
                    "fwd": {sym: {h: forward_return(prices, cal, sym, run["start"], h) for h in HORIZONS}
                            for sym in ETFS}})
    return out


def data_note(rows: list[dict], prices: dict) -> dict:
    """Price-calendar sessions since the first history date that have no status row, and each price file's last date."""
    cal = calendar(prices)
    have = {r["date"] for r in rows}
    first = rows[0]["date"]
    missing = [d for d in cal if d >= first and d not in have]
    return {"first": first, "n_missing": len(missing), "last_missing": missing[-1] if missing else None,
            "ends": {sym: (max(prices[sym]) if prices.get(sym) else None) for sym in ETFS}}


def gather(path: Path = WATCH_CSV, loader=default_loader) -> dict:
    rows = load_history(path)
    if not rows:
        return {"ok": False, "why": "no regime-watch history yet"}
    prices = {sym: loader(sym) for sym in ETFS}
    if not calendar(prices):
        return {"ok": False, "why": "no price files for SPY, QQQ or SMH"}
    runs = build_runs(rows, prices)
    last, cur = rows[-1], runs[0]
    cal = calendar(prices)
    return {"ok": True, "last": last, "held": sessions_between(cal, cur["start"], last["date"]) or cur["rows"],
            "runs": runs, "onsets": onsets(rows, prices), "note": data_note(rows, prices)}


# ── render ────────────────────────────────────────────────────────────────────
def fmt_pct(x) -> str:
    return DASH if x is None else f"{x * 100:+.1f}%"


def fmt_px(x) -> str:
    return DASH if x is None else f"{x:,.2f}"


def fmt_ret(x) -> str:
    return NOT_YET if x == NOT_YET else fmt_pct(x)


def _cls(x) -> str:
    return "num" if not isinstance(x, float) else "num " + ("good" if x > 0 else "bad" if x < 0 else "")


def _pill(status: str) -> str:
    return f'<span class="pill {STATUS_CLS.get(status, "null")}">{e(status)}</span>'


def _table(head: str, body: list[str]) -> str:
    return ('<div class="tablewrap"><table class="infra rw"><thead>' + head + "</thead><tbody>"
            + "".join(body) + "</tbody></table></div>")


def render_runs(runs: list[dict]) -> str:
    head = ('<tr><th rowspan="2">Status</th><th rowspan="2">Start</th><th rowspan="2">End</th>'
            '<th rowspan="2" class="num">Sessions</th>'
            + "".join(f'<th colspan="3" class="grp">{s}</th>' for s in ETFS) + "</tr><tr>"
            + "".join('<th class="num">Start</th><th class="num">End</th><th class="num">Change</th>' for _ in ETFS)
            + "</tr>")
    body = []
    for r in runs:
        cells = "".join(f'<td class="num">{fmt_px(r["prices"][s]["start"])}</td>'
                        f'<td class="num">{fmt_px(r["prices"][s]["end"])}</td>'
                        f'<td class="{_cls(r["prices"][s]["chg"])}">{fmt_pct(r["prices"][s]["chg"])}</td>'
                        for s in ETFS)
        logged = f' <span class="sub">({r["rows"]} logged)</span>' if r["rows"] != r["sessions"] else ""
        body.append(f'<tr><td>{_pill(r["status"])}</td><td>{e(r["start"])}</td><td>{e(r["end"])}</td>'
                    f'<td class="num">{r["sessions"]}{logged}</td>{cells}</tr>')
    return _table(head, body)


def render_onsets(ons: list[dict]) -> str:
    if not ons:
        return '<p class="nodata">No CONFIRMED signal in the history yet.</p>'
    head = ('<tr><th rowspan="2">Signal day</th>' + "".join(f'<th colspan="3" class="grp">{s}</th>' for s in ETFS)
            + "</tr><tr>" + "".join(f'<th class="num">{h} sessions</th>' for _ in ETFS for h in HORIZONS) + "</tr>")
    body = []
    for o in ons:
        cells = "".join(f'<td class="{_cls(o["fwd"][s][h])}">{fmt_ret(o["fwd"][s][h])}</td>'
                        for s in ETFS for h in HORIZONS)
        body.append(f'<tr><td>{e(o["date"])}</td>{cells}</tr>')
    return _table(head, body)


def render(g: dict, prereg_href: str | None = None) -> str:
    s = ['<section id="regime-watch"><h2>How did SPY, QQQ and SMH trade under each status?</h2>'
         '<p class="q">The regime-watch status set beside the three ETFs. It describes what already '
         'happened. It changes no trade.</p>']
    if not g["ok"]:
        s.append(f'<p class="nodata">No data. {e(g["why"])}.</p></section>')
        return "".join(s)
    last = g["last"]
    vix = last["vix_close"]
    try:
        vix = f"{float(vix):.1f}"
    except ValueError:
        vix = DASH
    s.append(f'<p class="big">{_pill(last["status"])} on {e(last["date"])}, held {g["held"]} session(s). '
             f'<span class="sub">{e(last["n_confirm"] or DASH)} market checks met, VIX close {e(vix)}, '
             f'mechanical read {e(last["mech_direction"] or DASH)} / {e(last["mech_vol"] or DASH)}.</span></p>')
    s.append('<h4>Status runs, newest first</h4>')
    s.append(render_runs(g["runs"]))
    s.append('<h4>Every CONFIRMED onset: return after the signal-day close</h4>')
    s.append(render_onsets(g["onsets"]))
    link = (f' <a href="{e(prereg_href)}">state_map registration</a>.' if prereg_href else "")
    s.append('<p class="sub">CONFIRMED marks a fall already under way. In the <code>state_map</code> study '
             "(2016 to 2026-09-22) SPY's average return after a bear signal was no worse than on an ordinary "
             f"day, and no signal turned on before a market top.{link}</p>")
    n = g["note"]
    gap = (f"{n['n_missing']} session(s) since {n['first']} have no status row; the most recent is "
           f"{n['last_missing']}." if n["n_missing"] else f"Every session since {n['first']} has a status row.")
    ends = ", ".join(f"{k} to {v or DASH}" for k, v in n["ends"].items())
    s.append(f'<p class="sub">{e(gap)} Session counts use the price calendar, not the history rows. '
             f'Price files reach: {e(ends)}. A change over a run uses the close on the exact start and end '
             f'dates, and a date with no close shows a dash.</p></section>')
    return "".join(s)
