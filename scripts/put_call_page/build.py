"""The dashboard's ETF put/call page: BaselineDaily premiums against each ETF's price.

Reads local files only: the BaselineDaily export and the underlying OHLC cache.
`gather` returns a plain dict and degrades to {"ok": False, "why": ...}, as the
dashboard's other gatherers do, so one bad file gives a "no data" card.

The ratio is put premium over call premium. It is computed here, and the tab
keeps its own columns, because `baseline_read` refuses any header change.

This page shows every date, including those from `era.SEAL_START`. The operator
chose that on 2026-11-06 (research/current.md). It reads flow and price only, never
a play's outcome, so `baseline_read`'s fixed forward computation is unchanged, but
that read is no longer blind.

The page is descriptive. It prints no forecast and no statistic.
"""
from __future__ import annotations

import csv
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.baseline import BASELINE_COLUMNS, normalize_sheet_date  # noqa: E402
from lib.parsing import to_float  # noqa: E402

PAGE_NAME = "put-call.html"
BASELINE_CSV = ROOT / "backtests" / "to_evaluate" / "analysis - BaselineDaily.csv"
ETFS = (
    ("SPY", "S&P 500"),
    ("QQQ", "Nasdaq 100"),
    ("IWM", "Russell 2000"),
    ("HYG", "High-yield credit"),
    ("TLT", "20+ year Treasuries"),
    ("GLD", "Gold"),
)
ASSETS = ROOT / "scripts" / "study_charts" / "assets"
CHART_JS = Path(__file__).with_name("chart.js")

_EXTRA_CSS = """
.pc-note{color:var(--ink-2);max-width:72ch;margin:0 0 10px}
.pc-controls{display:flex;flex-wrap:wrap;align-items:center;gap:16px;margin:22px 0 18px}
.pc-controls .legend{margin:0}
.pc-etf{margin-bottom:18px}
.pc-etf h3{font-size:18px}
.pc-etf h3 span{font-weight:400;color:var(--ink-2);font-size:14px;margin-left:8px}
.pc-meta{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);margin:2px 0 10px}
.pc-host svg{display:block;width:100%;height:auto;touch-action:pan-y}
.pc-host svg:focus-visible{outline:2px solid var(--s1);outline-offset:2px}
.pc-etf details{margin-top:8px;font-size:13px;color:var(--ink-2)}
.pc-etf summary{cursor:pointer}
.pc-table{max-height:320px;overflow:auto;margin-top:8px}
@media (max-width:600px){.wrap{padding:0 16px 64px}.panel{padding:14px}}
"""


def ratio(put: float | None, call: float | None) -> float | None:
    """Put premium over call premium. Blank unless both sides traded: a zero cannot sit on a log axis."""
    if put is None or call is None or put <= 0 or call <= 0:
        return None
    return round(put / call, 4)


def _default_bars(sym: str) -> dict:
    from scripts.backtest_study.lib.underlying import load_bars
    return load_bars(sym)


def _read_export(path: Path) -> tuple[list[dict], str]:
    """The export's rows and an empty string, or no rows and why it was refused."""
    if not Path(path).exists():
        return [], f"{Path(path).name} is missing. Run: python3 scripts/export_tabs.py --tabs BaselineDaily"
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    if header != BASELINE_COLUMNS:
        return [], f"{Path(path).name} header does not match lib.baseline.BASELINE_COLUMNS, so it was refused."
    return rows, ""


def gather(path: Path = BASELINE_CSV, bars=_default_bars) -> dict:
    """One date axis and one aligned series per ETF."""
    rows, why = _read_export(path)
    if why:
        return {"ok": False, "why": why}

    by_date: dict[str, dict] = {}
    for r in rows:
        d = normalize_sheet_date(r.get("date"))
        if d:
            by_date[d] = r
    if not by_date:
        return {"ok": False, "why": f"{Path(path).name} has no readable dates."}

    first, last = min(by_date), max(by_date)
    closes: dict[str, dict[str, float]] = {}
    for sym, _ in ETFS:
        closes[sym] = {k.isoformat(): b.c for k, b in bars(sym).items()
                       if first <= k.isoformat() <= last}

    # Every session with flow or a price, so a session with no flow shows as a gap.
    dates = sorted(set(by_date).union(*closes.values()))

    etfs = []
    for sym, name in ETFS:
        low = sym.lower()
        call, put, rat, close = [], [], [], []
        for d in dates:
            r = by_date.get(d, {})
            c, p = to_float(r.get(f"{low}_call_prem")), to_float(r.get(f"{low}_put_prem"))
            call.append(c)
            put.append(p)
            rat.append(ratio(p, c))
            close.append(closes[sym].get(d))
        with_flow = sum(1 for c, p in zip(call, put) if c is not None and p is not None)
        with_ratio = sum(1 for x in rat if x is not None)
        priced = [d for d, x in zip(dates, close) if x is not None]
        etfs.append({
            "sym": sym, "name": name, "call": call, "put": put, "ratio": rat, "close": close,
            "n_blank": len(dates) - with_flow,
            "n_no_ratio": with_flow - with_ratio,
            "last_price": priced[-1] if priced else None,
        })
    return {"ok": True, "dates": dates, "first": first, "last": last, "etfs": etfs}


def fragment(d: dict) -> str:
    """The page's <title>, <style> and body content, for `dashboard.document` to wrap."""
    css = (ASSETS / "page.css").read_text(encoding="utf-8") + _EXTRA_CSS
    head = f"<title>ETF Put/Call</title><style>{css}</style>"
    if not d.get("ok"):
        return (f'{head}<main class="wrap"><header class="masthead"><h1>ETF put/call</h1></header>'
                f'<p class="pc-note">No data: {html.escape(d.get("why", "unknown"))}</p></main>')
    payload = json.dumps(d, separators=(",", ":")).replace("</", "<\\/")
    kit = (ASSETS / "kit.js").read_text(encoding="utf-8")
    chart = CHART_JS.read_text(encoding="utf-8")
    return f"""{head}
<main class="wrap">
  <header class="masthead">
    <h1>ETF put/call</h1>
    <p class="pc-note">Daily put and call premium from BaselineDaily, against each ETF's closing price.
      The ratio is put premium over call premium, so above 1.0 means more put premium than call premium.</p>
    <p class="pc-note">This is Barchart's flagged flow, not whole-market volume. Bought and sold trades count alike,
      so put premium alone is not a bearish reading. The page is descriptive: baseline_read found that
      market-level flow forecasts nothing.</p>
    <p class="pc-note">Dates run {d['first']} to {d['last']}, the end of the local export.
      Viewing dates from 2026-09-23 means baseline_read's forward test is no longer blind.</p>
  </header>
  <div class="pc-controls" id="pc-controls"></div>
  <div id="pc-etfs"></div>
</main>
<script>window.__PUT_CALL__={payload};</script>
<script>{kit}</script>
<script>{chart}</script>"""


def write_page(out_dir: Path, document, pages: set[str] | None = None,
               path: Path = BASELINE_CSV, bars=_default_bars) -> Path:
    """Write the page under the dashboard's bar. `document` is `dashboard.document`."""
    dest = Path(out_dir) / PAGE_NAME
    dest.write_text(document(fragment(gather(path, bars)), "putcall", pages), encoding="utf-8")
    return dest
